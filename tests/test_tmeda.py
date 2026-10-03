"""Macleod, Bage, Meyer and Thomas 2024, Org. Lett. 26, 9564-9567 (doi:10.1021/acs.orglett.4c03591, CC BY 4.0).

A negative about a control method: TMEDA trapping, the field's standard test for hidden BH3 catalysis, gives false
negatives above 60 °C. Values pinned from the article and its Supporting Information: Me2S.BH3 control 9.6 mM/s and 87 %
at 60 °C against 0.3 mM/s and 4 % for the TMEDA adduct; 50 % at 80 °C and 94 % at 100 °C; 15 of 24 literature uses of
the test above 60 °C; 0.5 eq TMEDA leaves 11 % product at 100 °C for the alkene.
"""
from pathlib import Path

import pytest

from nrr.ingest.tmeda import build_tmeda_records, parse_amine_screen, parse_kinetics, parse_loading
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_tmeda_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def finding(records, slug, fid):
    return next(f for f in by_slug(records, slug)["findings"] if f["id"] == fid)


def test_parse_kinetics_pins_the_control_and_adduct_rates():
    k = {(r["substrate"], r["bh3_source"], r["temperature_c"]): r for r in parse_kinetics(ROOT / "curated/tmeda/kinetics.csv")}
    assert len(k) == 8
    assert k[("alkyne", "Me2S.BH3", 60)]["initial_rate_mm_s"] == 9.6 and k[("alkyne", "Me2S.BH3", 60)]["yield_pct"] == 87
    assert k[("alkyne", "TMEDA.(BH3)2", 60)]["initial_rate_mm_s"] == 0.3 and k[("alkyne", "TMEDA.(BH3)2", 60)]["yield_pct"] == 4
    assert k[("alkyne", "TMEDA.(BH3)2", 80)]["yield_pct"] == 50 and k[("alkyne", "TMEDA.(BH3)2", 100)]["yield_pct"] == 94
    assert k[("alkene", "TMEDA.(BH3)2", 60)]["initial_rate_mm_s"] == 0.02


def test_parse_amine_screen_and_loading():
    rows = parse_amine_screen(ROOT / "curated/tmeda/amine_screen.csv")
    assert len(rows) == 28
    inhibit = {(r["code"], r["temperature_c"]) for r in rows if r["inhibited"]}
    assert ("control", 70) in inhibit and ("control", 80) not in inhibit
    assert ("5a", 60) in inhibit and ("5a", 70) not in inhibit
    assert not any(code in {c for c, _ in inhibit} for code in ("5c", "5d", "Et3N", "Me3N"))
    load = parse_loading(ROOT / "curated/tmeda/loading.csv")
    assert len(load) == 9
    alkene_100 = {r["tmeda_equiv"]: r["yield_pct"] for r in load if r["substrate"] == "alkene" and r["temperature_c"] == 100}
    assert alkene_100 == {0.5: "11", 0.75: "9", 1.0: "7"}


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "acs-tmeda-path", "acs-tmeda-adduct-kinetics", "acs-tmeda-amine-screen", "acs-tmeda-loading", "acs-tmeda-literature-survey"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])
    assert all(r["domainTags"] == ["chemistry"] for r in records)


def test_adduct_inert_at_60_is_an_informative_negative(records):
    """At 60 °C the adduct does not catalyse: free-BH3 control passed (9.6 mM/s, 87 %), the no-catalyst background
    is clean, and the inhibition threshold (<5 % product by NMR) is a stated detection limit."""
    f = finding(records, "acs-tmeda-adduct-kinetics", "alkyne-60")
    assert f["outcomeClass"] == "negative-no-effect" and f["informativeness"] == "informative"
    assert f["effect"]["value"] == 0.3 and f["effect"]["unit"] == "mM/s" and "9.6" in f["effect"]["comparedTo"]
    assert f["controls"]["positive"]["kind"] == "designated" and f["controls"]["positive"]["passed"] is True
    assert "Me2S" in f["controls"]["positive"]["label"]
    assert f["controls"]["negative"]["kind"] == "background" and f["controls"]["negative"]["passed"] is True
    assert "5" in f["sensitivity"]
    assert f["conditions"]["temperatureC"] == 60


def test_adduct_catalyses_above_60(records):
    f80 = finding(records, "acs-tmeda-adduct-kinetics", "alkyne-80")
    f100 = finding(records, "acs-tmeda-adduct-kinetics", "alkyne-100")
    assert f80["outcomeClass"] == "positive" and f80["effect"]["value"] == 0.6 and f80["conditions"]["yieldPct"] == 50
    assert f100["effect"]["value"] == 4.56 and f100["conditions"]["yieldPct"] == 94
    a60 = finding(records, "acs-tmeda-adduct-kinetics", "alkene-60")
    assert a60["outcomeClass"] == "negative-no-effect" and a60["informativeness"] == "informative"


def test_the_test_itself_is_the_refuted_target(records):
    """How the record says 'this negative control is unreliable above 60 °C': the assay is the target of a refuted
    finding with the temperature limit in its conditions, and the path carries the valid range as applicability."""
    f = finding(records, "acs-tmeda-adduct-kinetics", "tmeda-test-false-negative-above-60")
    assert f["outcomeClass"] == "refuted" and f["informativeness"] == "not-applicable"
    assert f["target"]["type"] == "assay" and "TMEDA" in f["target"]["label"]
    assert f["conditions"]["validUpToC"] == 60 and f["conditions"]["falseNegativeFromC"] == 80
    assert {"acs-tmeda-adduct-kinetics#alkyne-80", "acs-tmeda-adduct-kinetics#alkene-100"} <= set(f["relatedFindings"])
    p = by_slug(records, "acs-tmeda-path")
    assert p["applicabilityConditions"]["tmedaInhibitionTestValidUpToC"] == 60
    assert any("80" in i for i in p["invalidators"]) or any("80" in s for s in p["applicabilityConditions"].values() if isinstance(s, str))


def test_hbpin_decomposes_at_80_so_the_background_control_fails_there(records):
    f = finding(records, "acs-tmeda-adduct-kinetics", "hbpin-thermal-decomposition")
    assert f["outcomeClass"] == "positive" and f["conditions"]["bh3ObservedFromC"] == 80
    screen = finding(records, "acs-tmeda-amine-screen", "amine-5c")
    assert screen["controls"]["negative"]["kind"] == "background"
    assert "70" in screen["controls"]["negative"]["note"] and "80" in screen["controls"]["negative"]["note"]


def test_no_amine_is_a_better_trap(records):
    overall = finding(records, "acs-tmeda-amine-screen", "better-trap")
    assert overall["outcomeClass"] == "negative-not-achievable" and overall["informativeness"] == "informative"
    assert overall["controls"]["positive"]["kind"] == "internal-positive"
    assert overall["effect"]["value"] == 0 and overall["effect"]["n"] == 6
    a = finding(records, "acs-tmeda-amine-screen", "amine-5a")
    assert a["outcomeClass"] == "partial" and a["conditions"]["inhibitsUpToC"] == 60
    c = finding(records, "acs-tmeda-amine-screen", "amine-5c")
    assert c["outcomeClass"] == "negative-no-effect" and c["conditions"].get("inhibitsUpToC") is None   # absent, never null
    assert by_slug(records, "acs-tmeda-amine-screen")["outcomeClass"] == "negative-not-achievable"


def test_higher_loading_is_partial(records):
    f = finding(records, "acs-tmeda-loading", "loading-alkene")
    assert f["outcomeClass"] == "partial"
    assert f["effect"]["value"] == 7 and f["effect"]["unit"] == "%" and f["conditions"]["tmedaEquiv"] == 1.0
    g = finding(records, "acs-tmeda-loading", "loading-alkyne")
    assert g["conditions"]["completeInhibitionAt"] == "0.5 eq TMEDA at 80 and 100 °C"


def test_literature_survey_quantifies_the_affected_tests(records):
    s = by_slug(records, "acs-tmeda-literature-survey")
    assert s["attemptType"] == "evidence-synthesis"
    stage = next(st for st in s["stages"] if st["stage"] == "literature-search")
    assert stage["recordsFound"] == 633 and stage["sourcesSearched"][0]["name"] == "SciFinder"
    f = finding(records, "acs-tmeda-literature-survey", "tests-above-60")
    assert f["effect"]["value"] == 15 and f["effect"]["n"] == 24
    refs = [src for src in s["sources"] if src["role"] == "reference" and src.get("note", "").startswith("SI reference")]
    assert len(refs) == 19
    assert any("does not say which" in n for n in s["provenanceNotes"])


def test_path_and_entities(records):
    p = by_slug(records, "acs-tmeda-path")
    assert p["pathType"] == "experiment" and p["outcomeClass"] == "partial"
    assert len(p["hasPart"]) == 4
    ents = {e["id"]: e for e in p["entities"]}
    assay = next(e for e in ents.values() if e["type"] == "assay")
    assert "TMEDA" in assay["label"]
    assert any(e["type"] == "compound" and "tetramethylethylenediamine" in e["label"].lower() for e in ents.values())


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
