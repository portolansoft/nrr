"""Facts pinned from Kolb, Reitman, Lane et al. 2024 (The Stacks) and its Zenodo deposits."""
from pathlib import Path

import pytest

from nrr.ingest.neuroimaging import build_neuroimaging_records, parse_trials
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_neuroimaging_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def test_parse_trials_reads_the_figure_legend_table():
    trials = parse_trials(ROOT / "curated/neuroimaging/trials.csv")
    assert len(trials) == 13
    assert sum(1 for t in trials if t["modality"] == "tactile") == 3
    assert sum(1 for t in trials if t["modality"] == "capsaicin") == 6   # 3 vehicle + 3 drug
    assert sum(1 for t in trials if t["modality"] == "histamine") == 4   # 2 vehicle + 2 drug


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "arcadia-neuroimaging-path", "arcadia-neuroimaging-tactile",
        "arcadia-neuroimaging-capsaicin", "arcadia-neuroimaging-histamine"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_tactile_findings_are_positive_and_contralateral(records):
    t = by_slug(records, "arcadia-neuroimaging-tactile")
    assert t["outcomeClass"] == "positive"
    assert len(t["findings"]) == 3
    rhl = next(f for f in t["findings"] if f["id"] == "tactile-rhl")
    assert rhl["outcomeClass"] == "positive"
    assert rhl["controls"]["negative"]["kind"] == "within-subject"
    assert "1-3%" in rhl["effect"]["value"] or "1-3%" in str(rhl["effect"].get("note", ""))


def test_tactile_stage_records_the_troubleshooting_loop(records):
    t = by_slug(records, "arcadia-neuroimaging-tactile")
    stage = next(s for s in t["stages"] if s["stage"] == "experiment")
    assert len(stage["protocolAdaptations"]) == 4
    assert any("isoflurane" in a for a in stage["protocolAdaptations"])


def test_capsaicin_is_positive_against_a_paired_vehicle(records):
    c = by_slug(records, "arcadia-neuroimaging-capsaicin")
    assert c["outcomeClass"] == "positive"
    lhl = next(f for f in c["findings"] if f["id"] == "capsaicin-lhl")
    assert lhl["outcomeClass"] == "positive"
    assert lhl["controls"]["negative"]["kind"] == "vehicle"
    assert lhl["controls"]["positive"]["kind"] == "internal-positive"    # the tactile gate
    assert lhl["target"]["identifier"] == "pubchem:CID1548943"
    assert "confound" in " ".join(c["provenanceNotes"]).lower()


def test_histamine_is_inconclusive_because_the_vehicle_produced_the_same_signal(records):
    h = by_slug(records, "arcadia-neuroimaging-histamine")
    assert h["outcomeClass"] == "inconclusive-controls-failed"
    agg = next(f for f in h["findings"] if f["id"] == "histamine-overall")
    assert agg["informativeness"] == "uninformative"
    assert "negative control not clean" in agg["informativenessReason"]
    assert agg["controls"]["positive"]["passed"] is True                 # the positive control did pass
    assert agg["controls"]["negative"]["passed"] is False
    assert "irreproducible-across-trials" in agg["failureModes"]
    assert "signal-below-noise" in agg["failureModes"]
    assert agg["target"]["identifier"] == "pubchem:CID5818"


def test_every_finding_carries_run_ids_that_chain_to_a_checksummed_deposit(records):
    for slug in ("arcadia-neuroimaging-tactile", "arcadia-neuroimaging-capsaicin", "arcadia-neuroimaging-histamine"):
        for f in by_slug(records, slug)["findings"]:
            ptrs = [d for e in f["evidence"] for d in e.get("data", [])]
            if f["id"] == "histamine-overall":
                continue
            assert ptrs, (slug, f["id"])
            assert all(p["checksum"].startswith("md5:") for p in ptrs)
            assert any(p.get("runId") for p in ptrs)


def test_arrive_reporting_fields_are_present_and_honest(records):
    h = by_slug(records, "arcadia-neuroimaging-histamine")
    f = h["findings"][0]
    assert f["reportingGuideline"]
    assert f["blinding"]
    assert f["preregistration"] == "none"


def test_uncited_imaging_session_is_an_untried_branch(records):
    path = by_slug(records, "arcadia-neuroimaging-path")
    branches = [b for b in path["untriedBranches"] if b["status"] == "data-deposited-not-analysed"]
    assert len(branches) == 1
    assert "2024-03-06" in branches[0]["description"]
    assert branches[0]["dataAvailable"][0]["size"] == 20174619604


def test_path_is_partial_but_iced_for_a_technical_gap(records):
    path = by_slug(records, "arcadia-neuroimaging-path")
    assert path["outcomeClass"] == "partial"
    assert path["abandonmentReasons"] == ["technical-gap"]
    assert len(path["nextSteps"]) == 5
    assert len(path["openQuestions"]) == 2


def test_animal_governance_is_recorded(records):
    path = by_slug(records, "arcadia-neuroimaging-path")
    assert "CRADL" in path["governance"]["complianceIds"][0]
    ac = by_slug(records, "arcadia-neuroimaging-histamine")["applicabilityConditions"]
    assert ac["organism"] == "NCBITaxon:10090"
    assert ac["sex"] == "female"
    assert "isoflurane" in ac["anesthesia"]


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
