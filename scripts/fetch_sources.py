"""Fetch the source artefacts the converters read, into raw/. Network required.

Usage: uv run python scripts/fetch_sources.py [--study robin-damd|arcadia-alcalase|all] [--dest raw]

robin-damd: shallow-clones Future-House/robin at the pinned commit and copies the dAMD sample runs (Apache-2.0),
reduces the 49 MB Finch results JSON to metadata, downloads the Nature supplementary workbook (CC BY-NC-ND 4.0, local
use only; never commit it) and the ENA run table for PRJNA1464762.
arcadia-alcalase: downloads the Zenodo CSVs and record metadata (CC BY 4.0) and the Stacks page text.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ROBIN_REPO = "https://github.com/Future-House/robin"
ROBIN_COMMIT = "4a5cce310f3bc7663a67117db88af43b84733ffe"
RUNS = ["dry_age-related_macular_degeneration_2025-05-28_16-51", "dry_age-related_macular_degeneration_2025-05-29_12-11"]
MOESM3 = "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-026-10652-y/MediaObjects/41586_2026_10652_MOESM3_ESM.xlsx"
ENA_FIELDS = "run_accession,sample_accession,experiment_accession,sample_title,sample_alias,library_strategy,library_layout,instrument_platform,instrument_model,read_count,base_count,first_public,scientific_name,tax_id,fastq_ftp,fastq_md5,sra_md5"
UA = {"User-Agent": "portolan-nrr-pilot/0.2 (contact@portolansoft.com)"}


def get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=120, **kw)
    r.raise_for_status()
    return r


def finch_meta(results_json: Path) -> dict:
    d = json.loads(results_json.read_text(encoding="utf-8"))
    out = {}
    for step, v in d.items():
        out[step] = {"task_ids": v["task_ids"], "success_rate": v.get("success_rate"), "tasks": []}
        for t in v["task_responses"]:
            try:
                an = json.loads(t["agent_name"])
            except Exception:
                an = t["agent_name"]
            out[step]["tasks"].append({k: t.get(k) for k in ["task_id", "status", "created_at", "job_name", "environment_name", "build_owner", "public"]}
                                      | {"agent": an, "query_sha256": hashlib.sha256(t["query"].encode()).hexdigest(), "query_chars": len(t["query"])})
        out[step]["query"] = v["task_responses"][0]["query"]
    return out


def fetch_robin(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "robin"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", ROBIN_REPO], check=True)
        subprocess.run(["git", "-C", str(repo), "fetch", "-q", "--depth", "1", "origin", ROBIN_COMMIT], check=True)
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "FETCH_HEAD"], check=True)
        for run in RUNS:
            src, dst = repo / "robin_output" / run, dest / "robin_output" / run
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("results_*.json"))
            for rj in (src / "data_analysis").glob("results_*.json") if (src / "data_analysis").exists() else []:
                (dst / "data_analysis" / "finch_trajectories_meta.json").write_text(json.dumps(finch_meta(rj), indent=1), encoding="utf-8")
        (dest / "robin_output" / "LICENSE").write_bytes((repo / "LICENSE").read_bytes())
        print(f"robin_output copied from {ROBIN_COMMIT[:7]}")
    supp = dest / "supplementary"
    supp.mkdir(exist_ok=True)
    (supp / "41586_2026_10652_MOESM3_ESM.xlsx").write_bytes(get(MOESM3).content)
    print("supplementary workbook downloaded (CC BY-NC-ND 4.0, local use only)")
    sra = dest / "sra"
    sra.mkdir(exist_ok=True)
    (sra / "ena_read_run_PRJNA1464762.tsv").write_text(get("https://www.ebi.ac.uk/ena/portal/api/search", params={
        "result": "read_run", "query": "study_accession=PRJNA1464762", "fields": ENA_FIELDS, "format": "tsv", "limit": 100}).text, encoding="utf-8")
    (sra / "ena_study_PRJNA1464762.json").write_text(get("https://www.ebi.ac.uk/ena/portal/api/search", params={
        "result": "study", "query": "study_accession=PRJNA1464762", "fields": "study_accession,secondary_study_accession,study_title,study_description,center_name,first_public,last_updated", "format": "json"}).text, encoding="utf-8")
    print("ENA run table downloaded")


def fetch_alcalase(dest: Path) -> None:
    z = dest / "zenodo"
    z.mkdir(parents=True, exist_ok=True)
    rec = get("https://zenodo.org/api/records/22238548").json()
    (z / "record_22238548.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    for f in rec["files"]:
        if f["key"].endswith(".csv"):
            (z / f["key"]).write_bytes(get(f["links"]["self"]).content)
    pub = dest / "pub"
    pub.mkdir(exist_ok=True)
    s = get("https://thestacks.org/publications/informative-failure-alcalase-crispr-chlamydomonas").text
    s2 = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S)
    txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s2)))
    (pub / "arcadia-pdu7-q2zz.extracted.txt").write_text(txt, encoding="utf-8")
    print("Zenodo CSVs and Stacks text downloaded")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="all", choices=["all", "robin-damd", "arcadia-alcalase"])
    ap.add_argument("--dest", default=str(ROOT / "raw"))
    a = ap.parse_args()
    dest = Path(a.dest)
    if a.study in ("all", "robin-damd"):
        fetch_robin(dest / "robin")
    if a.study in ("all", "arcadia-alcalase"):
        fetch_alcalase(dest / "alcalase")
    return 0


if __name__ == "__main__":
    sys.exit(main())
