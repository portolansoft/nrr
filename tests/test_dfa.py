"""Facts pinned from Morin, Patton et al. 2024, the divergent fungal actin pub (The Stacks).

Encoded as a convergence test: comparative genomics across a kingdom, no experiment, species as the unit of
observation, and a negative of the form 'no association with any of six traits'.
"""
from pathlib import Path

import pytest

from nrr.ingest.dfa import build_dfa_records, parse_traits
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_dfa_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def finding(records, slug, fid):
    return next(f for f in by_slug(records, slug)["findings"] if f["id"] == fid)


def test_parse_traits():
    t = parse_traits(ROOT / "curated/dfa/traits.csv")
    assert len(t) == 6
    assert t["growth form"]["n_species"] == 24
    assert t["growth form"]["best_aic"] == 69.34
    assert t["spore length"]["p_value_slope"] == 0.64
    assert sum(1 for v in t.values() if v["data_type"] == "continuous") == 2


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "arcadia-dfa-path", "arcadia-dfa-cluster-expansion",
        "arcadia-dfa-distribution", "arcadia-dfa-trait-association"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_one_finding_per_trait_plus_a_headline(records):
    ta = by_slug(records, "arcadia-dfa-trait-association")
    ids = {f["id"] for f in ta["findings"]}
    assert len(ids) == 7
    assert "trait-overall" in ids
    assert "trait-growth-form" in ids and "trait-spore-length" in ids


def test_discrete_traits_record_the_model_selection(records):
    f = finding(records, "arcadia-dfa-trait-association", "trait-growth-form")
    assert f["effect"]["value"] == 69.34
    assert "86.65" in f["effect"]["comparedTo"]
    assert "Akaike" in f["effect"]["test"]
    assert f["effect"]["n"] == 24


def test_continuous_traits_record_the_slope_p_value(records):
    f = finding(records, "arcadia-dfa-trait-association", "trait-spore-length")
    assert f["effect"]["pValue"] == 0.64
    assert f["effect"]["n"] == 10


def test_the_rule_names_the_missing_positive_control(records):
    """The authors blame trait coverage and DFA-absence errors. The rule additionally surfaces that no
    positive control was run, so a null result cannot be separated from a method that cannot detect anything."""
    ta = by_slug(records, "arcadia-dfa-trait-association")
    assert ta["outcomeClass"] == "inconclusive-no-positive-control"
    overall = finding(records, "arcadia-dfa-trait-association", "trait-overall")
    assert overall["informativeness"] == "uninformative"
    assert "no positive control" in overall["informativenessReason"]
    assert overall["controls"]["positive"]["kind"] == "none"


def test_traits_are_typed_as_phenotypes(records):
    ents = {e["id"]: e for e in by_slug(records, "arcadia-dfa-trait-association")["entities"]}
    trait_ents = [e for e in ents.values() if e["type"] == "phenotype"]
    assert len(trait_ents) == 6


def test_trait_databases_are_recorded_as_searched_sources(records):
    ta = by_slug(records, "arcadia-dfa-trait-association")
    stage = next(s for s in ta["stages"] if s.get("sourcesSearched"))
    names = {s["name"] for s in stage["sourcesSearched"]}
    assert "Fun Fun" in names and "TimeTree" in names


def test_cluster_expansion_is_positive_and_carries_the_protein_identifiers(records):
    ce = by_slug(records, "arcadia-dfa-cluster-expansion")
    assert ce["outcomeClass"] == "positive"
    f = finding(records, "arcadia-dfa-cluster-expansion", "extended-set")
    assert f["effect"]["value"] == 436
    ids = {e["id"] for e in ce["entities"]}
    assert "uniprot:P60709" in ids                      # the human seed protein
    assert "uniprot:A0A401L4A6" in ids                  # a representative divergent actin


def test_distribution_finding_is_positive_but_carries_its_own_caveat(records):
    f = finding(records, "arcadia-dfa-distribution", "distribution-labile")
    assert f["outcomeClass"] == "positive"
    assert "overestimat" in f["note"]


def test_path_is_iced_for_a_resource_constraint(records):
    p = by_slug(records, "arcadia-dfa-path")
    assert p["outcomeClass"] == "partial"
    assert p["abandonmentReasons"] == ["resource-constraint"]
    assert len(p["nextSteps"]) == 3


def test_absence_definition_is_in_the_applicability_envelope(records):
    ac = by_slug(records, "arcadia-dfa-trait-association")["applicabilityConditions"]
    assert "6,000" in ac["absenceDefinition"]
    assert ac["speciesAnalysed"] == 102


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
