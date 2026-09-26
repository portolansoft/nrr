"""Facts pinned from Cheveralls et al. 2026, the Raman batch-effects pub (The Stacks)."""
from pathlib import Path

import pytest

from nrr.ingest.raman import build_raman_records, parse_results, parse_strains
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_raman_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def finding(records, slug, fid):
    return next(f for f in by_slug(records, slug)["findings"] if f["id"] == fid)


def test_parsers():
    strains = parse_strains(ROOT / "curated/raman/strains.csv")
    assert len(strains) == 9
    assert sum(1 for s in strains if s["species"] == "S. pombe") == 6
    results = parse_results(ROOT / "curated/raman/results.csv")
    assert len(results) == 7
    assert results[("strain", "standard-5-fold", "uncorrected")]["mcc_median"] == 0.79
    assert results[("plate", "leave-one-strain-out", "uncorrected")]["mcc_median"] == 1.0


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "arcadia-raman-path", "arcadia-raman-strain-classification",
        "arcadia-raman-species-classification", "arcadia-raman-batch-effect"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_the_headline_number_is_recorded_as_refuted_not_positive(records):
    """MCC 0.79 under standard cross-validation is the number a less careful study would have published.
    The study's own later analysis refutes it, so it is neither a positive result nor an absent one."""
    f = finding(records, "arcadia-raman-strain-classification", "strain-standard-cv")
    assert f["outcomeClass"] == "refuted"
    assert f["informativeness"] == "not-applicable"
    assert f["effect"]["value"] == 0.79
    assert f["effect"]["range"] == [0.71, 0.93]
    assert "confounded" in f["failureModes"]


def test_the_real_strain_negative_is_blocked_by_the_adversarial_control(records):
    f = finding(records, "arcadia-raman-strain-classification", "strain-lopo")
    assert f["outcomeClass"] == "inconclusive-controls-failed"
    assert f["controls"]["negative"]["kind"] == "adversarial-label"
    assert f["controls"]["negative"]["passed"] is False
    assert f["controls"]["positive"]["kind"] == "known-positive-task"
    assert f["controls"]["positive"]["passed"] is True
    assert f["effect"]["value"] == 0.32


def test_after_batch_correction_the_only_thing_missing_is_a_detection_limit(records):
    f = finding(records, "arcadia-raman-strain-classification", "strain-lopo-corrected")
    assert f["controls"]["negative"]["passed"] is True      # adversarial control now clean
    assert f["controls"]["positive"]["passed"] is True
    assert f["informativenessReason"] == "no sensitivity or power statement"
    assert f["outcomeClass"] == "inconclusive-underpowered"
    assert "train-test-leakage" in f["failureModes"]


def test_the_same_data_and_model_give_opposite_answers_by_validation_scheme(records):
    """The point of the study, and the reason a registry has to record the analysis configuration."""
    strain = by_slug(records, "arcadia-raman-strain-classification")
    std = finding(records, "arcadia-raman-strain-classification", "strain-standard-cv")
    lopo = finding(records, "arcadia-raman-strain-classification", "strain-lopo")
    assert std["conditions"]["crossValidation"] != lopo["conditions"]["crossValidation"]
    assert std["conditions"]["model"] == lopo["conditions"]["model"]
    assert std["conditions"]["dataset"] == lopo["conditions"]["dataset"]
    assert std["effect"]["value"] > 2 * lopo["effect"]["value"]
    assert any("cross-validation" in n for n in strain["provenanceNotes"])


def test_species_classification_is_the_positive_control_and_it_passes(records):
    sp = by_slug(records, "arcadia-raman-species-classification")
    assert sp["outcomeClass"] == "positive"
    f = finding(records, "arcadia-raman-species-classification", "species-lopo")
    assert f["effect"]["value"] == 0.97
    assert f["outcomeClass"] == "positive"


def test_batch_effect_detection_is_a_positive_finding_about_a_confound(records):
    b = by_slug(records, "arcadia-raman-batch-effect")
    assert b["outcomeClass"] == "positive"
    f = finding(records, "arcadia-raman-batch-effect", "plate-loso")
    assert f["effect"]["value"] == 1.0
    assert "chance" in f["effect"]["comparedTo"]
    corrected = finding(records, "arcadia-raman-batch-effect", "plate-loso-corrected")
    assert corrected["effect"]["value"] == 0.10


def test_path_is_partial_and_not_iced(records):
    p = by_slug(records, "arcadia-raman-path")
    assert p["outcomeClass"] == "partial"
    assert "abandonmentReasons" not in p
    assert len(p["nextSteps"]) == 3          # the authors' recommendations
    assert p["pathType"] == "mixed"


def test_licence_differs_between_the_pub_and_its_code_deposit(records):
    p = by_slug(records, "arcadia-raman-path")
    lic = {s["role"]: s.get("license") for s in p["sources"] if s.get("license")}
    assert "creativecommons.org/licenses/by/4.0" in lic["source-publication"]
    assert lic["code-repository"] == "MIT"


def test_entities_span_both_yeasts_and_the_human_orthologs(records):
    ids = {e["id"] for e in by_slug(records, "arcadia-raman-strain-classification")["entities"]}
    assert {"NCBITaxon:4932", "NCBITaxon:4896"} <= ids
    assert "HGNC:12472" in ids and "HGNC:186" in ids


def test_ai_use_records_participation_in_analysis_not_just_prose(records):
    p = by_slug(records, "arcadia-raman-path")
    tools = {t["name"]: t for t in p["aiUseDeclaration"]["tools"]}
    assert "ideation" in tools["Claude"]["purpose"]


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
