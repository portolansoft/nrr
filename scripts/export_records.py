"""Export one study's records for the public dataset repository (portolansoft/nrr-records).

Usage: uv run python scripts/export_records.py --study arcadia-alcalase --dest ../nrr-records
Writes <dest>/<study>/{records,crates,deposits}/, <dest>/<study>/manifest.json and <dest>/<study>/ro-crate-metadata.json
(a collection crate listing the records). Only studies whose sources permit redistribution should be exported.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nrr.crate import to_crate  # noqa: E402
from nrr.deposit import deposit_payload  # noqa: E402
from nrr.ingest.alcalase import build_alcalase_records  # noqa: E402
from nrr.ingest.neuroimaging import build_neuroimaging_records  # noqa: E402
from nrr.ingest.dfa import build_dfa_records  # noqa: E402
from nrr.ingest.raman import build_raman_records  # noqa: E402
from nrr.ingest.tmeda import build_tmeda_records  # noqa: E402
from nrr.ingest.zeolite import build_zeolite_records  # noqa: E402
from nrr.resolve import Resolver  # noqa: E402
from nrr.schema import PROFILE_URI, validate  # noqa: E402

BUILDERS = {"arcadia-alcalase": build_alcalase_records, "arcadia-neuroimaging": build_neuroimaging_records,
            "arcadia-raman": build_raman_records, "arcadia-dfa": build_dfa_records,
            "acs-zeolite": build_zeolite_records, "acs-tmeda": build_tmeda_records}
LICENSES = {"arcadia-alcalase": "https://creativecommons.org/licenses/by/4.0/",
            "arcadia-neuroimaging": "https://creativecommons.org/licenses/by/4.0/",
            "arcadia-raman": "https://creativecommons.org/licenses/by/4.0/",
            "arcadia-dfa": "https://creativecommons.org/licenses/by/4.0/",
            "acs-zeolite": "https://creativecommons.org/licenses/by/4.0/",
            "acs-tmeda": "https://creativecommons.org/licenses/by/4.0/"}


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", required=True, choices=sorted(BUILDERS))
    ap.add_argument("--dest", required=True)
    a = ap.parse_args()
    if "robin" in a.study:
        raise SystemExit("robin-damd records are not exported: source licence is CC BY-NC-ND 4.0")
    resolver = Resolver(ROOT / "curated" / "identifiers.json", online=False)
    records = BUILDERS[a.study](ROOT, resolver)
    dest = Path(a.dest) / a.study
    for sub in ("records", "crates", "deposits"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    for rec in records:
        assert validate(rec) == [], rec["slug"]
        (dest / "records" / f"{rec['slug']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        (dest / "crates" / rec["slug"]).mkdir(exist_ok=True)
        (dest / "crates" / rec["slug"] / "ro-crate-metadata.json").write_text(json.dumps(to_crate(rec), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (dest / "deposits" / f"{rec['slug']}.json").write_text(json.dumps(deposit_payload(rec), indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    path = next(r for r in records if r["kind"] == "path")
    src_pub = next(s for s in path["sources"] if s["role"] == "source-publication")
    manifest = {
        "study": a.study, "profile": PROFILE_URI, "license": LICENSES[a.study], "generatedBy": {"repository": "https://github.com/portolansoft/nrr", "commit": git_commit(), "script": "scripts/export_records.py"},
        "sourcePublication": {"identifier": src_pub["identifier"], "label": src_pub.get("label"), "license": src_pub.get("license")},
        "records": [{"slug": r["slug"], "id": r["@id"], "kind": r["kind"], "attemptType": r.get("attemptType"), "outcomeClass": r["outcomeClass"], "findings": len(r.get("findings", []))} for r in records],
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    collection = {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": [
            {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"}, "about": {"@id": "./"}},
            {"@id": "./", "@type": "Dataset", "name": f"Portolan NRR records: {path['title']}", "description": path["question"], "license": {"@id": LICENSES[a.study]},
             "datePublished": path["dateCreated"][:10], "conformsTo": {"@id": PROFILE_URI}, "isBasedOn": {"@id": "https://doi.org/" + src_pub["identifier"][4:]},
             "hasPart": [{"@id": f"crates/{r['slug']}/ro-crate-metadata.json"} for r in records], "publisher": {"@id": "#portolan"}},
            {"@id": "#portolan", "@type": "Organization", "name": "Portolan Software", "url": "https://portolansoft.com/"},
            {"@id": "https://doi.org/" + src_pub["identifier"][4:], "@type": "ScholarlyArticle", "name": src_pub.get("label"), "license": src_pub.get("license")},
        ] + [{"@id": f"crates/{r['slug']}/ro-crate-metadata.json", "@type": "Dataset", "name": r["title"], "identifier": r["@id"], "nrr:outcomeClass": r["outcomeClass"]} for r in records],
    }
    (dest / "ro-crate-metadata.json").write_text(json.dumps(collection, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"exported {len(records)} records for {a.study} to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
