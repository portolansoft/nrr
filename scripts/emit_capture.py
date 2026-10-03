"""Emit capture-time deposit payloads from an open system's run output.

Usage:
  uv run python scripts/emit_capture.py robin raw/robin/robin_output/<run folder> [--config capture/robin-config.yaml] [--out out/capture]
  uv run python scripts/emit_capture.py datahub <run.json> --claim capture/datahub-claim.yaml [--out out/capture]

Writes one nrr_deposit payload per record and prints the capture-profile verdict for each. Offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nrr.capture.profile import check_capture  # noqa: E402
from nrr.deposit import deposit_payload  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["robin", "datahub"])
    ap.add_argument("path")
    ap.add_argument("--config", help="robin: run configuration YAML (models, commit, operator)")
    ap.add_argument("--claim", help="datahub: the claim YAML the agent or person adds to the run")
    ap.add_argument("--out", default=str(ROOT / "out" / "capture"))
    a = ap.parse_args()
    if a.source == "robin":
        from nrr.capture.robin import emit_robin_run
        cfg = yaml.safe_load(Path(a.config).read_text()) if a.config else None
        records = emit_robin_run(Path(a.path), run_config=cfg)
    else:
        from nrr.capture.datahub import emit_datahub_run
        claim = yaml.safe_load(Path(a.claim).read_text())
        records = emit_datahub_run(json.loads(Path(a.path).read_text()), claim)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    worst = 0
    for rec in records:
        errors, warnings = check_capture(rec)
        (out / f"{rec['slug']}.json").write_text(json.dumps(deposit_payload(rec), indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{rec['slug']}: {'OK' if not errors else 'NOT CAPTURE-COMPLETE'}; {len(errors)} errors, {len(warnings)} warnings")
        for e in errors:
            print("  error:", e)
        for w in warnings:
            print("  warning:", w)
        worst = max(worst, 1 if errors else 0)
    print(f"wrote {len(records)} deposit payloads to {out}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
