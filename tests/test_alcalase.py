"""Facts pinned from Caddell et al. 2026 (The Stacks) and its Zenodo deposit."""
from pathlib import Path

import pytest

from nrr.ingest.alcalase import build_alcalase_records, parse_colony_index, parse_wall_permeability, rule_of_three
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_alcalase_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def test_parse_wall_permeability():
    rows = parse_wall_permeability(ROOT / "raw/alcalase/zenodo/wall_permeability_data.csv")
    assert len(rows) == 8
    alc = next(r for r in rows if r["culture"] == "flask" and r["treatment"] == "Alcalase")
    assert alc["efficiency_percent"] == pytest.approx(23.36)


def test_parse_colony_index_summarises_sequencing():
    s = parse_colony_index(ROOT / "raw/alcalase/zenodo/Chlamydomonas_CRISPR-HDR_plate_colony_image_index.csv")
    assert s["colonies"] == 386
    assert s["sequenced"] == 40
    assert s["edited"] == 0
    assert s["pcr_band_yes"] == 176  # raw index; Table 5 reports 172/191 after excluding evaporated wells


def test_rule_of_three():
    assert rule_of_three(40) == pytest.approx(7.5)


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "arcadia-alcalase-path", "arcadia-alcalase-wall-permeability", "arcadia-alcalase-viability",
        "arcadia-alcalase-transformation", "arcadia-alcalase-hdr-knockin", "arcadia-alcalase-visual-screen",
        "arcadia-alcalase-culture-format",
    }
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_hdr_finding_is_inconclusive_for_want_of_a_positive_control(records):
    hdr = by_slug(records, "arcadia-alcalase-hdr-knockin")
    assert hdr["outcomeClass"] == "inconclusive-no-positive-control"
    f = hdr["findings"][0]
    assert f["informativeness"] == "uninformative"
    assert f["controls"]["positive"]["kind"] == "none"
    assert "7.5" in f["sensitivity"]


def test_transformation_finding_is_negative_with_transformation_failed(records):
    tr = by_slug(records, "arcadia-alcalase-transformation")
    f = next(f for f in tr["findings"] if "Alcalase" in f["target"]["label"])
    assert f["outcomeClass"] == "negative-not-achievable"
    assert "transformation-failed" in f["failureModes"]
    assert f["controls"]["positive"]["kind"] == "internal-positive"


def test_path_carries_next_steps_questions_and_icebox_reasons(records):
    path = by_slug(records, "arcadia-alcalase-path")
    assert path["outcomeClass"] == "abandoned"
    assert len(path["untriedBranches"]) == 3
    assert len(path["openQuestions"]) == 3
    assert set(path["abandonmentReasons"]) == {"technical-gap", "strategic-misalignment"}
    assert path["aiUseDeclaration"]["tools"]


def test_zenodo_files_are_data_pointers_with_checksums(records):
    path = by_slug(records, "arcadia-alcalase-path")
    dep = next(s for s in path["sources"] if s["role"] == "data-deposit")
    assert len(dep["data"]) == 10
    assert all(d["checksum"].startswith("md5:") for d in dep["data"])


def test_organism_and_loci_are_shared_identifiers(records):
    tr = by_slug(records, "arcadia-alcalase-transformation")
    ids = {e["id"] for e in tr["entities"]}
    assert "NCBITaxon:3055" in ids
    assert "phytozome:Cre04.g231026" in ids
