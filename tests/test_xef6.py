"""Koch, Hoß, Schnakenburg, Karttunen and Kraus 2026, Inorg. Chem. 65, 15126-15135 (doi:10.1021/acs.inorgchem.6c02072,
CC BY 4.0).

A classic synthetic dead end whose by-product is a characterised new compound. Pinned values: CCDC 2477117; P2_1/n with
a = 8.4517, b = 8.9602, c = 15.4691 A, beta = 95.392 degrees, V = 1166.27 A3, Z = 4 at 100 K, R(F) = 0.0176; Xe-F-Xe
163.15 degrees; five reaction conditions described in prose with no run count; [XeF7]+ bands predicted at 588, 647 and
503 cm-1 and absent; [XeF7][RuF6] formation energy -572 (CP) / -138 kJ/mol.
"""
from pathlib import Path

import pytest

from nrr.ingest.xef6 import build_xef6_records, parse_conditions
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_xef6_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def finding(records, slug, fid):
    return next(f for f in by_slug(records, slug)["findings"] if f["id"] == fid)


def test_parse_conditions_keeps_prose_locators_and_no_run_counts():
    rows = parse_conditions(ROOT / "curated/xef6/conditions.csv")
    assert len(rows) == 5
    assert all(r["runs_reported"] == "not stated" for r in rows)
    assert all(r["locator"].startswith("Results and Discussion, paragraph") for r in rows)
    assert rows[0]["ruf6_mmol"] == 0.14 and rows[0]["xef6_mmol"] == 0.41
    assert rows[2]["ruf6_mmol"] == 0.46 and rows[2]["xef6_mmol"] == 0.49
    assert all(r["xe_oxidation_state"] == "VI" for r in rows)


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "acs-xef6-path", "acs-xef6-oxidation-attempts", "acs-xef6-xe2f11-ruf6", "acs-xef6-thermodynamics"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_each_prose_condition_is_a_finding_with_its_paragraph(records):
    att = by_slug(records, "acs-xef6-oxidation-attempts")
    cond = [f for f in att["findings"] if f["id"].startswith("condition-")]
    assert len(cond) == 5
    for f in cond:
        assert f["outcomeClass"] == "inconclusive-no-positive-control"
        assert f["informativenessReason"] == "no positive control; no negative control; no sensitivity or power statement"
        assert f["replicates"]["note"].startswith("no run count is reported")
        assert f["evidence"][0]["locator"].startswith("Results and Discussion, paragraph")
        assert f["target"]["label"].startswith("xenon(VIII)")
    c1 = finding(records, "acs-xef6-oxidation-attempts", "condition-excess-xef6-ahf")
    assert c1["conditions"]["ruf6Mmol"] == 0.14 and c1["conditions"]["xef6Mmol"] == 0.41
    assert c1["conditions"]["product"] == "[Xe2F11][RuF6]"
    assert c1["failureModes"] == ["decomposition"]
    assert "588" in c1["controls"]["positive"]["note"] or "588" in c1.get("note", "")
    assert att["outcomeClass"] == "inconclusive-no-positive-control"
    assert "wetLabRuns" not in att["cost"] and "not reported" in att["cost"]["note"]


def test_f2_evolution_is_the_positive_observation(records):
    f = finding(records, "acs-xef6-oxidation-attempts", "f2-evolved")
    assert f["outcomeClass"] == "positive" and "KI" in f["evidence"][0]["quote"]


def test_the_by_product_is_a_positive_attempt_derived_from_the_failure(records):
    rec = by_slug(records, "acs-xef6-xe2f11-ruf6")
    assert rec["outcomeClass"] == "positive"
    assert any(r["type"] == "wasDerivedFrom" and r["target"] == by_slug(records, "acs-xef6-oxidation-attempts")["@id"] for r in rec["relations"])
    xs = finding(records, "acs-xef6-xe2f11-ruf6", "crystal-structure")
    assert xs["target"]["identifier"] == "ccdc:2477117"
    assert xs["conditions"]["spaceGroup"] == "P2_1/n (no. 14)" and xs["conditions"]["a"] == 8.4517 and xs["conditions"]["z"] == 4
    assert xs["effect"]["value"] == 0.0176 and xs["effect"]["metric"].startswith("R(F)")
    geo = finding(records, "acs-xef6-xe2f11-ruf6", "cation-geometry")
    assert geo["effect"]["value"] == 163.15 and geo["effect"]["unit"] == "degrees"
    dep = next(s for s in rec["sources"] if s["role"] == "data-deposit")
    assert dep["identifier"] == "ccdc:2477117"
    ents = {e["id"]: e for e in rec["entities"]}
    assert ents["ccdc:2477117"]["type"] == "compound" and ents["ccdc:2477117"]["scheme"] == "CCDC"


def test_thermodynamics_explains_without_resolving(records):
    rec = by_slug(records, "acs-xef6-thermodynamics")
    assert rec["attemptType"] == "computational" and rec["outcomeClass"] == "partial"
    f = finding(records, "acs-xef6-thermodynamics", "xef7-ruf6-feasible")
    assert f["outcomeClass"] == "positive" and f["effect"]["value"] == -572 and f["effect"]["unit"] == "kJ/mol"
    assert "-138" in f["effect"]["note"] or "-138" in f["effect"]["comparedTo"]
    g = finding(records, "acs-xef6-thermodynamics", "xef7-unstable-to-f2")
    assert g["effect"]["value"] == 191
    w = finding(records, "acs-xef6-thermodynamics", "why-it-fails")
    assert w["outcomeClass"] == "partial" and "not right, yet" in w["evidence"][0]["quote"]


def test_prior_dead_ends_are_screened_and_cited(records):
    p = by_slug(records, "acs-xef6-path")
    assert p["outcomeClass"] == "negative-not-achievable" and p["pathType"] == "mixed"
    labels = {s["label"] for s in p["screened"]}
    assert {"F2", "[KrF]+", "[NiF3]+", "RuF6"} == labels
    assert all(s["reason"] == "prior-art-found" for s in p["screened"] if s["label"] != "RuF6")
    assert next(s for s in p["screened"] if s["label"] == "RuF6")["reason"] == "selected-for-testing"
    assert "doi:10.1016/0022-1902(70)80296-2" in {s["identifier"] for s in p["sources"]}
    assert len(p["hasPart"]) == 3
    ents = {e["label"]: e for e in p["entities"]}
    assert any(e["id"].startswith("pubchem:") and "xenon hexafluoride" in e["label"].lower() for e in ents.values())


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
