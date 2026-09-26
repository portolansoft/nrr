"""The database is the reuse surface: these are the questions another agent would ask."""
from pathlib import Path

import pytest

from nrr.db import load, query
from nrr.ingest.alcalase import build_alcalase_records
from nrr.ingest.robin import build_robin_records
from nrr.resolve import Resolver

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "raw" / "robin" / "robin_output").exists(), reason="raw/robin not fetched (scripts/fetch_sources.py --study robin-damd)")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    resolver = Resolver(ROOT / "curated/identifiers.json", online=False)
    records = build_robin_records(ROOT, resolver) + build_alcalase_records(ROOT, resolver)
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
