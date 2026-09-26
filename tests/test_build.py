import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "raw" / "robin" / "robin_output").exists(), reason="raw/robin not fetched (scripts/fetch_sources.py --study robin-damd)")


def run_build(out_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "build.py"), "--out", str(out_dir)], capture_output=True, text=True, cwd=ROOT)


def test_build_writes_records_crates_deposits_and_report(tmp_path):
    out = tmp_path / "out"
    r = run_build(out)
    assert r.returncode == 0, r.stderr[-2000:]
    records = sorted((out / "records").glob("*.json"))
    crates = sorted((out / "crates").glob("*/ro-crate-metadata.json"))
    deposits = sorted((out / "mcp" / "deposits").glob("*.json"))
    assert len(records) == 30 and len(crates) == 30 and len(deposits) == 30
    manifest = json.loads((out / "mcp" / "manifest.json").read_text())
    assert manifest["recordCount"] == 30 and manifest["tool"] == "nrr_deposit"
    report = (out / "validation-report.md").read_text()
    assert "0 invalid" in report
    assert (out / "portolan.sqlite").exists()
    assert (out / "records.jsonl").exists()


def test_build_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert run_build(a).returncode == 0 and run_build(b).returncode == 0
    for pa in sorted((a / "records").glob("*.json")):
        pb = b / "records" / pa.name
        assert pa.read_bytes() == pb.read_bytes(), pa.name
    assert (a / "records.jsonl").read_bytes() == (b / "records.jsonl").read_bytes()


def test_deposit_payload_shape(tmp_path):
    out = tmp_path / "out"
    assert run_build(out).returncode == 0
    dep = json.loads(next((out / "mcp" / "deposits").glob("*.json")).read_text())
    assert dep["tool"] == "nrr_deposit"
    args = dep["arguments"]
    assert args["record"]["profile"] == "https://portolansoft.com/profile/nrr/0.2"
    assert args["crate"]["@graph"][0]["@id"] == "ro-crate-metadata.json"
    assert args["idempotencyKey"] == args["record"]["@id"]
