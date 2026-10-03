"""The capture profile and the Robin emitter.

The profile is the minimum an agent must write at run end. The Robin emitter is tested on the two sample run folders
in raw/robin (fetched by scripts/fetch_sources.py; tests skip without them). Pinned values come from the run folders
themselves: run 1 has 10 assay strategies and 45 pairwise assay judgements; its Finch analysis metadata names
anthropic/claude-3-7-sonnet-20250219 with five trajectories in step d20ee48e.
"""
import copy
from pathlib import Path

import pytest
import yaml

from nrr.capture.profile import check_capture
from nrr.schema import validate
from tests.factories import minimal_attempt

ROOT = Path(__file__).resolve().parents[1]
RUN1 = ROOT / "raw/robin/robin_output/dry_age-related_macular_degeneration_2025-05-28_16-51"
RUN2 = ROOT / "raw/robin/robin_output/dry_age-related_macular_degeneration_2025-05-29_12-11"
needs_robin = pytest.mark.skipif(not RUN1.exists(), reason="raw/robin not fetched")


def capture_ready() -> dict:
    rec = minimal_attempt()
    rec["dateCreated"] = "2026-05-01T12:00:00Z"
    rec["stages"] = [{"stage": "experiment", "startTime": "2026-05-01T09:00:00Z", "performedBy": [{"name": "lab robot", "type": "software-agent", "role": "experiment-execution", "version": "1.4.0"}]}]
    rec["performers"] = [{"name": "lab robot", "type": "software-agent", "role": "experiment-execution", "version": "1.4.0"}]
    rec["findings"][0]["evidence"][0]["data"] = [{"label": "plate_read.csv", "checksum": "sha256:" + "a" * 64, "runId": "run-1"}]
    return rec


def test_a_complete_capture_record_has_no_errors():
    errors, warnings = check_capture(capture_ready())
    assert errors == [] and warnings == []


def test_capture_requires_raw_evidence_pointers():
    rec = capture_ready()
    del rec["findings"][0]["evidence"][0]["data"]
    errors, _ = check_capture(rec)
    assert any("checksum or runId" in e for e in errors)


def test_capture_requires_a_timestamped_stage_and_identified_software():
    rec = capture_ready()
    del rec["stages"][0]["startTime"]
    del rec["performers"][0]["version"]
    errors, _ = check_capture(rec)
    assert any("startTime or endTime" in e for e in errors)
    assert any("without model, commit or version" in e for e in errors)


def test_a_negative_must_state_sensitivity_or_say_why_not():
    rec = capture_ready()
    del rec["findings"][0]["sensitivity"]
    errors, warnings = check_capture(rec)
    assert any("no note saying why" in e for e in errors)
    rec["findings"][0]["note"] = "no detection limit was estimated for this run"
    errors, warnings = check_capture(rec)
    assert errors == [] and any("the rule will mark it uninformative" in w for w in warnings)


def test_schema_problems_are_capture_errors():
    rec = capture_ready()
    rec["outcomeClass"] = "vibes"
    errors, _ = check_capture(rec)
    assert any(e.startswith("schema:") for e in errors)


@pytest.fixture(scope="module")
def records():
    if not RUN1.exists():
        pytest.skip("raw/robin not fetched")
    from nrr.capture.robin import emit_robin_run
    cfg = yaml.safe_load((ROOT / "capture/robin-config.yaml").read_text())
    return emit_robin_run(RUN1, run_config=cfg)


@needs_robin
class TestRobinEmitter:

    def test_four_attempts_all_valid_and_capture_complete(self, records):
        assert [r["slug"].split("16-51-")[1] for r in records] == ["assay-selection", "candidates-r1", "candidates-r2", "data-analysis"]
        for r in records:
            assert validate(r) == []
            errors, _ = check_capture(r)
            assert errors == [], (r["slug"], errors)
        assert all(r["dateCreated"] == "2025-05-28T16:51:00Z" for r in records)
        assert {r["studyId"] for r in records} == {"robin-run-dry-age-related-macular-degeneration-2025-05-28-16-51"}

    def test_assay_round_pins_the_run_folder(self, records):
        a = records[0]
        assert a["screenedSummary"] == {"proposed": 10, "pairwiseJudgements": 45}
        assert len(a["screened"]) == 10 and sum(1 for s in a["screened"] if s["decision"] == "included") == 1
        assert all(s["proposedBy"] == "robin-assay-round" for s in a["screened"])
        ptrs = a["findings"][0]["evidence"][0]["data"]
        assert all(p["checksum"].startswith("sha256:") for p in ptrs)
        assert any(p["label"] == "experimental_assay_ranking_results.csv" for p in ptrs)

    def test_proposer_is_stated_not_inferred(self, records):
        r1 = records[1]
        assert all(s["proposedBy"] == "robin-round-1" for s in r1["screened"])
        assert all("rank" in s["score"] and "wins" in s["score"] for s in r1["screened"] if "rank" in s["score"])
        assert r1["screenedSummary"]["ranked"] == len([s for s in r1["screened"] if "rank" in s["score"]])

    def test_models_come_from_config_for_proposal_and_from_metadata_for_analysis(self, records):
        r1 = records[1]
        names = {p["name"]: p for p in r1["performers"]}
        assert names["hypothesis synthesis model"]["model"] == "o4-mini"
        assert names["ranking judge model"]["model"] == "claude-3-7-sonnet"
        assert names["Robin"]["commit"] == "4a5cce310f3bc7663a67117db88af43b84733ffe"
        da = records[3]
        finch = next(p for p in da["performers"] if p["trajectoryIds"] and len(p["trajectoryIds"]) == 5)
        assert finch["model"] == "anthropic/claude-3-7-sonnet-20250219"
        assert finch["platformJob"] == "job-futurehouse-data-analysis-crow-high"
        assert any(s.get("endTime") for s in da["stages"])

    def test_without_config_the_profile_names_the_gap(self):
        from nrr.capture.robin import emit_robin_run
        records = emit_robin_run(RUN1)
        errors, _ = check_capture(records[1])
        assert sum("without model, commit or version" in e for e in errors) == 3
        errors_da, _ = check_capture(records[3])
        assert errors_da == []                      # the analysis step carries its own model name in the run output

    def test_second_run_without_an_experimental_round(self):
        from nrr.capture.robin import emit_robin_run
        records = emit_robin_run(RUN2, run_config=yaml.safe_load((ROOT / "capture/robin-config.yaml").read_text()))
        assert [r["slug"].split("12-11-")[1] for r in records] == ["assay-selection", "candidates-r1"]
        assert all(validate(r) == [] for r in records)

    def test_ids_are_content_addresses_and_deterministic(self, records):
        from nrr.capture.robin import emit_robin_run
        from nrr.identity import content_address
        again = emit_robin_run(RUN1, run_config=yaml.safe_load((ROOT / "capture/robin-config.yaml").read_text()))
        assert [r["@id"] for r in again] == [r["@id"] for r in records]
        assert all(r["@id"] == content_address(r) for r in records)


DATAHUB_RUN = ROOT / "raw/datahub/spectramax-id5-plate-reader_260721_OD750_AAA.run.json"


@pytest.fixture(scope="module")
def record():
    import json
    from nrr.capture.datahub import emit_datahub_run
    run = json.loads(DATAHUB_RUN.read_text())
    claim = yaml.safe_load((ROOT / "capture/datahub-claim-example.yaml").read_text())
    return emit_datahub_run(run, claim, files_dir=ROOT / "raw/datahub/files", hub_url="http://localhost:3000")[0]


class TestDataHubEmitter:
    RUN = DATAHUB_RUN

    def test_valid_and_capture_complete(self, record):
        assert validate(record) == []
        errors, warnings = check_capture(record)
        assert errors == [], errors
        assert record["dateCreated"] == "2026-10-03T18:09:19.397Z"       # the run's acquired_at, not the ingest default

    def test_measurement_layer_comes_from_data_hub(self, record):
        ptrs = record["findings"][0]["evidence"][0]["data"]
        assert {p["label"] for p in ptrs} == {"spectramax_plate_reader_endpoint.xls", "260721_OD750_AAA_raw_well_data.csv"}
        assert all(p["runId"] == "spectramax-id5-plate-reader/260721_OD750_AAA" for p in ptrs)
        csv = next(p for p in ptrs if p["label"].endswith(".csv"))
        assert csv["checksum"] == "sha256:47fe482ef5bcd36da156d8d5781431a8f87379cb26620f74331f35bb7edd33b2"
        assert csv["size"] == 1595 and csv["path"].startswith("spectramax-id5-plate-reader/260721_OD750_AAA/")
        stage = record["stages"][0]
        assert stage["stage"] == "instrument-capture" and stage["parameters"]["measurement_mode"] == "Absorbance"
        assert stage["performedBy"][0]["name"] == "Alice Zimmerman"

    def test_claim_layer_is_what_the_rule_reads(self, record):
        f = record["findings"][0]
        assert f["outcomeClass"] == "negative-no-effect" and f["informativeness"] == "informative"
        assert f["controls"]["positive"]["kind"] == "designated"
        assert any("EXAMPLE" in n for n in record["provenanceNotes"])

    def test_without_file_bytes_the_pointer_says_no_checksum(self):
        import json
        from nrr.capture.datahub import emit_datahub_run
        run = json.loads(self.RUN.read_text())
        claim = yaml.safe_load((ROOT / "capture/datahub-claim-example.yaml").read_text())
        rec = emit_datahub_run(run, claim)[0]
        ptrs = rec["findings"][0]["evidence"][0]["data"]
        assert all("checksum" not in p and "no per-file checksum" in p["note"] for p in ptrs)
        assert check_capture(rec)[0] == []                                 # runId alone satisfies the profile

    def test_a_claim_without_sensitivity_is_refused_by_the_profile(self):
        import json
        from nrr.capture.datahub import emit_datahub_run
        run = json.loads(self.RUN.read_text())
        claim = yaml.safe_load((ROOT / "capture/datahub-claim-example.yaml").read_text())
        del claim["sensitivity"]
        rec = emit_datahub_run(run, claim)[0]
        assert rec["findings"][0]["outcomeClass"] == "inconclusive-underpowered"
        errors, _ = check_capture(rec)
        assert any("no note saying why" in e for e in errors)
