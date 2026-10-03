"""Altundal et al. 2025, Chem. Mater. 37, 9689-9702 (doi:10.1021/acs.chemmater.5c01751, CC BY 4.0).

Values pinned here are read from the article (Europe PMC JATS, PMC12747119) and its Supporting Information:
42 phase determinations across SI Tables S18, S20, S21 and S22, every one amorphous or a non-target phase; MTW
ranked 13th in the prediction for QG001780m2; Model 2 specificity 99 percent and sensitivity 21 percent.
"""
from pathlib import Path

import pytest

from nrr.ingest.zeolite import build_zeolite_records, parse_candidates, parse_models, parse_syntheses
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_zeolite_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def finding(records, slug, fid):
    return next(f for f in by_slug(records, slug)["findings"] if f["id"] == fid)


def test_parse_syntheses_covers_every_si_table_row():
    rows = parse_syntheses(ROOT / "curated/zeolite/syntheses.csv")
    assert len(rows) == 42
    by_table = {}
    for r in rows:
        by_table.setdefault(r["table"], []).append(r)
    assert len(by_table["S18"]) == 16 and all(r["phase"] == "amorphous" for r in by_table["S18"])
    assert len(by_table["S20"]) == 12 and all(r["phase"] == "amorphous" for r in by_table["S20"])
    assert sum(1 for r in by_table["S21"] if "MTW" in r["phase"]) == 2
    assert sum(1 for r in by_table["S21"] + by_table["S22"] if "MOR" in r["phase"]) == 4
    assert not any(r["phase"] in ("STF", "IFR", "AEI", "CHA") for r in rows)
    assert max(r["time_days"] for r in rows) == 50
    assert {r["temperature_c"] for r in by_table["S18"]} == {150, 175, 200}


def test_parse_candidates_and_models():
    cands = parse_candidates(ROOT / "curated/zeolite/candidates.csv")
    assert len(cands) == 18
    assert sum(1 for c in cands if c["target"] == "STF") == 13
    assert sum(1 for c in cands if c["synthesized"]) == 3
    assert all(c["rank_of_target"] in (2, 3) for c in cands)        # STF or IFR is never the most stable phase
    models = parse_models(ROOT / "curated/zeolite/models.csv")
    m2 = {(m["dataset"], m["class"]): m for m in models if m["model"] == "Model 2"}
    assert m2[("train", "non-STF OSDA")]["accuracy_pct"] == 99
    assert m2[("train", "STF OSDA")]["accuracy_pct"] == 21
    m3 = next(m for m in models if m["model"] == "Model 3" and m["dataset"] == "external")
    assert m3["classified_non_stf"] == 436 and m3["n"] == 547


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "acs-zeolite-path", "acs-zeolite-osda-screen", "acs-zeolite-stf-synthesis",
        "acs-zeolite-ifr-synthesis-qg001780m", "acs-zeolite-ifr-synthesis-qg001780m2"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])
    assert all("chemistry" in r["domainTags"] and "materials" in r["domainTags"] for r in records)
    assert all(r["sourceLicense"] == "CC BY 4.0" for r in records)


def test_the_computational_predictions_are_recorded_as_refuted(records):
    """The authors' own verdict: 'our predictions from calculations must be considered a failure'."""
    screen = by_slug(records, "acs-zeolite-osda-screen")
    assert screen["attemptType"] == "computational"
    assert screen["outcomeClass"] == "refuted"
    f = finding(records, "acs-zeolite-osda-screen", "prediction-qg001780m2")
    assert f["outcomeClass"] == "refuted" and f["informativeness"] == "not-applicable"
    assert f["conditions"]["predictedPhases"] == ["CHA", "AEI", "IFR"]
    assert f["conditions"]["observedPhases"] and "MTW" in " ".join(f["conditions"]["observedPhases"])
    assert f["conditions"]["mtwRankInPrediction"] == 13
    assert "model-did-not-generalize" in f["failureModes"]
    assert any(r.startswith("acs-zeolite-ifr-synthesis-qg001780m2#") for r in f["relatedFindings"])


def test_the_screen_carries_the_classifier_validation_as_findings(records):
    f = finding(records, "acs-zeolite-osda-screen", "classifier-model-2")
    assert f["outcomeClass"] == "partial"
    assert f["effect"]["value"] == 21 and f["effect"]["metric"].startswith("sensitivity")
    assert "99" in f["effect"]["comparedTo"]
    landscape = finding(records, "acs-zeolite-osda-screen", "esyn-landscape")
    assert landscape["effect"]["n"] == 78
    assert landscape["effect"]["value"] == 0                         # OSDAs for which STF is the most stable phase


def test_synthesis_negatives_are_inconclusive_for_want_of_a_positive_control(records):
    """No known-good OSDA was run through the same hydrothermal protocol, and no XRD detection limit is stated.
    The classifier's sensitivity and specificity describe the screen, not the synthesis, so they do not count."""
    stf = by_slug(records, "acs-zeolite-stf-synthesis")
    assert stf["attemptType"] == "wet-lab"
    f = finding(records, "acs-zeolite-stf-synthesis", "stf-not-formed")
    assert f["outcomeClass"] == "inconclusive-no-positive-control"
    assert f["informativeness"] == "uninformative"
    assert f["informativenessReason"] == "no positive control; no negative control; no sensitivity or power statement"
    assert f["controls"]["positive"]["kind"] == "none"
    assert "sensitivity" not in f
    assert set(f["failureModes"]) == {"phase-not-formed", "decomposition"}
    assert f["replicates"]["note"].startswith("16 phase determinations")
    assert f["effect"]["value"] == 0 and f["effect"]["n"] == 16


def test_ifr_with_qg001780m2_records_the_wrong_phases(records):
    f = finding(records, "acs-zeolite-ifr-synthesis-qg001780m2", "ifr-not-formed")
    assert f["outcomeClass"] == "inconclusive-no-positive-control"
    assert set(f["failureModes"]) == {"phase-not-formed", "impurity-phase"}
    assert f["effect"]["n"] == 14
    phases = f["conditions"]["phasesObserved"]
    assert "MOR" in phases and "dense phase" in phases and any(p.startswith("ZSM-12 (MTW)") for p in phases)
    rec = by_slug(records, "acs-zeolite-ifr-synthesis-qg001780m2")
    assert any("Table 2" in n and "MOR" in n for n in rec["provenanceNotes"])


def test_each_synthesis_row_is_evidence_with_its_si_locator(records):
    f = finding(records, "acs-zeolite-ifr-synthesis-qg001780m", "ifr-not-formed")
    locs = {e["locator"] for e in f["evidence"]}
    assert "SI Table S20, entry 6" in locs and len(locs) == 6


def test_frameworks_are_materials_and_osdas_are_compounds(records):
    ents = {e["id"]: e for e in by_slug(records, "acs-zeolite-path")["entities"]}
    assert ents["iza:STF"]["type"] == "material" and ents["iza:IFR"]["type"] == "material"
    assert ents["iza:MTW"]["type"] == "material"
    assert ents["inchikey:QHGWEBIGEQBZPY-RWMBFGLXNA-N"]["type"] == "compound"
    assert "spiro" in ents["inchikey:QHGWEBIGEQBZPY-RWMBFGLXNA-N"]["label"]


def test_screened_candidates_name_which_were_synthesised(records):
    screen = by_slug(records, "acs-zeolite-osda-screen")
    items = screen["screened"]
    assert len(items) == 18
    chosen = [i for i in items if i["decision"] == "included"]
    assert {i["label"].split(" ")[0] for i in chosen} == {"qhgwebigeqbzpy-rwmbfglxna-n", "qg001780m", "qg001780m2"}
    assert all(i["reason"] == "selected-for-testing" for i in chosen)
    assert all(i["score"]["rank"] in (2, 3) for i in items)
    assert screen["screenedSummary"]["osdbInPapers"] == 610 and screen["screenedSummary"]["osdbNotInPapers"] == 580


def test_path_headline_and_cost(records):
    p = by_slug(records, "acs-zeolite-path")
    assert p["pathType"] == "mixed"
    assert p["outcomeClass"] == "negative-not-achievable"
    assert p["cost"]["wetLabRuns"] == 42
    assert p["cost"]["wallClockDays"] == 50
    assert len(p["hasPart"]) == 4
    assert any("stereoisomer" in n for n in p["provenanceNotes"])
    assert any("cyclohexyl" in n for n in p["provenanceNotes"])


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
