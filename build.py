"""Build the pilot corpus: records, RO-Crates, MCP deposit payloads, SQLite store, validation report.

Usage: uv run python build.py [--out out]
Runs fully offline against curated/identifiers.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from nrr.crate import to_crate  # noqa: E402
from nrr.db import load, query, query_names  # noqa: E402
from nrr.deposit import deposit_payload  # noqa: E402
from nrr.ingest.alcalase import build_alcalase_records  # noqa: E402
from nrr.ingest.neuroimaging import build_neuroimaging_records  # noqa: E402
from nrr.ingest.raman import build_raman_records  # noqa: E402
from nrr.ingest.robin import build_robin_records  # noqa: E402
from nrr.resolve import Resolver  # noqa: E402
from nrr.schema import validate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--study", default="all", choices=["all", "robin-damd", "arcadia-alcalase", "arcadia-neuroimaging", "arcadia-raman"])
    args = ap.parse_args()
    out = Path(args.out)
    for sub in ("records", "crates", "mcp/deposits"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    resolver = Resolver(ROOT / "curated" / "identifiers.json", online=False)
    records = []
    if args.study in ("all", "robin-damd"):
        if not (ROOT / "raw" / "robin" / "robin_output").exists():
            print("raw/robin is missing; run scripts/fetch_sources.py --study robin-damd first", file=sys.stderr)
            return 2
        records += build_robin_records(ROOT, resolver)
    if args.study in ("all", "arcadia-alcalase"):
        records += build_alcalase_records(ROOT, resolver)
    if args.study in ("all", "arcadia-neuroimaging"):
        records += build_neuroimaging_records(ROOT, resolver)
    if args.study in ("all", "arcadia-raman"):
        records += build_raman_records(ROOT, resolver)

    problems = {}
    for rec in records:
        p = validate(rec)
        if p:
            problems[rec["slug"]] = p
        (out / "records" / f"{rec['slug']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        cdir = out / "crates" / rec["slug"]
        cdir.mkdir(exist_ok=True)
        (cdir / "ro-crate-metadata.json").write_text(json.dumps(to_crate(rec), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (out / "mcp" / "deposits" / f"{rec['slug']}.json").write_text(json.dumps(deposit_payload(rec), indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    with open(out / "records.jsonl", "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "tool": "nrr_deposit",
        "profile": "https://portolansoft.com/profile/nrr/0.2",
        "recordCount": len(records),
        "studies": sorted({r["studyId"] for r in records}),
        "records": [{"slug": r["slug"], "id": r["@id"], "kind": r["kind"], "attemptType": r.get("attemptType"), "outcomeClass": r["outcomeClass"],
                     "findings": len(r.get("findings", [])), "screened": len(r.get("screened", [])), "deposit": f"deposits/{r['slug']}.json"} for r in records],
        "order": "paths first, then attempts; each deposit is idempotent on the record id",
        "unresolvedIdentifiers": sorted(set(resolver.misses)),
    }
    (out / "mcp" / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    load(records, out / "portolan.sqlite")

    n_find = sum(len(r.get("findings", [])) for r in records)
    n_scr = sum(len(r.get("screened", [])) for r in records)
    lines = ["# Validation report", "", f"Records: {len(records)} ({len(records) - len(problems)} valid, {len(problems)} invalid)",
             f"Findings: {n_find}; screened items: {n_scr}", ""]
    if problems:
        for slug, p in problems.items():
            lines.append(f"## {slug}")
            lines += [f"- {x}" for x in p]
    lines += ["", "## Findings by outcome class and informativeness", "", "| study | outcomeClass | informativeness | n |", "|---|---|---|---|"]
    for row in query(out / "portolan.sqlite", "outcome_summary"):
        lines.append(f"| {row['study_id']} | {row['outcome_class']} | {row['informativeness']} | {row['n']} |")
    lines += ["", "## Unresolved identifier lookups (offline cache misses)", ""] + [f"- {m}" for m in sorted(set(resolver.misses))] or ["- none"]
    lines += ["", "## Named queries available", ""] + [f"- {q}" for q in query_names()]
    (out / "validation-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} records to {out} ({len(problems)} invalid)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
