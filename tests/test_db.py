"""The database is the reuse surface: these are the questions another agent would ask."""
from pathlib import Path

import pytest

from nrr.db import load, query
from nrr.ingest.alcalase import build_alcalase_records
from nrr.ingest.neuroimaging import build_neuroimaging_records
from nrr.ingest.raman import build_raman_records
from nrr.ingest.robin import build_robin_records
from nrr.resolve import Resolver

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "raw" / "robin" / "robin_output").exists(), reason="raw/robin not fetched (scripts/fetch_sources.py --study robin-damd)")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    resolver = Resolver(ROOT / "curated/identifiers.json", online=False)
    records = (build_robin_records(ROOT, resolver) + build_alcalase_records(ROOT, resolver)
               + build_neuroimaging_records(ROOT, resolver) + build_raman_records(ROOT, resolver))
    path = tmp_path_factory.mktemp("db") / "portolan.sqlite"
    load(records, path)
    return path


def test_prior_art_for_ripasudil_finds_three_records(db):
    rows = query(db, "prior_art", target="ripasudil")
    slugs = {r["slug"] for r in rows}
    assert {"robin-damd-screen-r2-arpe19", "robin-damd-screen-rpesc", "robin-damd-candidates-r2"} <= slugs


def test_prior_art_by_identifier(db):
    rows = query(db, "prior_art_by_identifier", identifier="pubchem:CID9863672")
    assert any(r["outcome_class"] == "positive" for r in rows)


def test_records_by_taxon_separates_the_studies(db):
    rows = query(db, "by_entity", entity_id="NCBITaxon:3055")
    assert rows and all(r["study_id"] == "arcadia-alcalase" for r in rows)
    rows = query(db, "by_entity", entity_id="NCBITaxon:9606")
    assert rows and all(r["study_id"] == "robin-damd" for r in rows)


def test_uninformative_negatives_across_studies(db):
    rows = query(db, "uninformative_negatives")
    slugs = {r["slug"] for r in rows}
    assert "arcadia-alcalase-hdr-knockin" in slugs
    assert "robin-damd-finch-flow-r1" in slugs


def test_full_text_search_hits_alcalase_transformation(db):
    rows = query(db, "search", text="alcalase chlamydomonas")
    assert rows[0]["slug"].startswith("arcadia-alcalase")


def test_negative_results_with_dose_for_a_target(db):
    rows = query(db, "negatives_for_target", target="Fingolimod")
    assert rows and all(r["outcome_class"] == "negative-no-effect" for r in rows)
    assert any("1 µM" in (r["dose"] or "") for r in rows)


def test_agent_attribution_query(db):
    rows = query(db, "by_performer", name="Deep Research")
    assert {r["slug"] for r in rows} == {"deep-research-damd-candidates"}


def test_open_questions_and_untried_branches(db):
    rows = query(db, "open_branches")
    assert any(r["study_id"] == "arcadia-alcalase" for r in rows)
    assert any("MLN120B" in r["description"] for r in rows)


def test_reference_status_table(db):
    rows = query(db, "references_status", study_id="arcadia-alcalase")
    assert rows and all(r["integrity"] in ("none", "unknown") for r in rows)


def test_three_studies_fail_the_informativeness_rule_in_three_different_ways(db):
    """The rule discriminates: each study in the corpus trips a different clause, so 'uninformative'
    is a diagnosis rather than a blanket refusal."""
    rows = query(db, "uninformative_negatives")
    reason_by_study = {}
    for r in rows:
        reason_by_study.setdefault(r["study_id"], set()).add(r["informativeness_reason"].split(";")[0].strip())
    assert reason_by_study["arcadia-alcalase"] == {"no positive control"}
    assert reason_by_study["robin-damd"] == {"positive control failed"}
    assert reason_by_study["arcadia-neuroimaging"] == {"negative control not clean"}


def test_a_passing_positive_control_does_not_rescue_a_dirty_negative_control(db):
    rows = [r for r in query(db, "uninformative_negatives") if r["study_id"] == "arcadia-neuroimaging"]
    assert rows and all(r["positive_control_kind"] == "internal-positive" for r in rows)
    assert all(r["positive_control_passed"] == 1 for r in rows)


def test_deposited_but_unanalysed_data_spans_two_studies(db):
    rows = [r for r in query(db, "open_branches") if r["status"] == "data-deposited-not-analysed"]
    assert {r["study_id"] for r in rows} == {"robin-damd", "arcadia-neuroimaging"}
    assert all(r["data_pointers"] > 0 for r in rows)


def test_four_studies_produce_four_distinct_diagnoses(db):
    """Every clause of the informativeness rule now fires on real published data, and the Raman study is the
    first where the controls behave and the only thing missing is a detection limit."""
    reasons = {r["informativeness_reason"] for r in query(db, "uninformative_negatives")}
    assert "no positive control" in reasons                                    # Alcalase
    assert "positive control failed" in reasons                                # Robin / Finch
    assert "negative control not clean; no sensitivity or power statement" in reasons   # neuroimaging, Raman
    assert "no sensitivity or power statement" in reasons                      # Raman, batch-corrected


def test_computational_controls_are_in_use_alongside_wet_lab_ones(db):
    import sqlite3
    con = sqlite3.connect(db)
    pos = {r[0] for r in con.execute("select distinct positive_control_kind from findings where positive_control_kind is not null")}
    neg = {r[0] for r in con.execute("select distinct negative_control_kind from findings where negative_control_kind is not null")}
    assert {"designated", "internal-positive", "known-positive-task"} <= pos
    assert {"vehicle", "within-subject", "adversarial-label"} <= neg


def test_a_refuted_finding_is_not_counted_as_an_uninformative_negative(db):
    slugs_and_ids = {(r["slug"], r["finding_id"]) for r in query(db, "uninformative_negatives")}
    assert ("arcadia-raman-strain-classification", "strain-standard-cv") not in slugs_and_ids
