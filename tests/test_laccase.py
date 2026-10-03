"""Steffens et al. 2023, Environ. Sci. Technol. Lett. 10, 337-342 (doi:10.1021/acs.estlett.3c00173, CC BY 4.0).

The cleanest fit to the informativeness rule among the ACS studies: a failure to replicate reported PFOA and PFOS
degradation by a laccase mediator system, with a positive control that is a different substrate (carbamazepine,
about 35 % removed, p < 0.001) and an artefact mechanism (sorption to the enzyme) shown by mass balance. Pinned
values: PFOA p = 0.29 against the untreated control; apparent loss 18 +/- 2 % (PFOA) and 34 +/- 4 % (PFOS); 99 +/- 14 %
and 111 +/- 11 % mass recovered at 96 h; PFOS sorption to the reactor 40 +/- 12 % in the enzyme-free control.
"""
from pathlib import Path

import pytest

from nrr.ingest.laccase import build_laccase_records, parse_experiments, parse_mass_balance
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    return build_laccase_records(ROOT, Resolver(ROOT / "curated/identifiers.json", online=False))


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


def finding(records, slug, fid):
    return next(f for f in by_slug(records, slug)["findings"] if f["id"] == fid)


def test_parse_mass_balance_pins_the_si_tables():
    mb = parse_mass_balance(ROOT / "curated/laccase/mass_balance.csv")
    assert len(mb) == 24
    assert mb[("PFOA", "TvL + HBT", "subsample (24 hours)")] == (82, 1.7)
    assert mb[("PFOS", "TvL + HBT", "subsample (24 hours)")] == (66, 3.5)
    assert mb[("PFOS", "TvL", "subsample (24 hours)")] == (65, 3.1)
    assert mb[("PFOS", "control", "reactor extract")] == (40, 12.1)
    assert mb[("PFOA", "TvL + HBT", "delta solution")] == (13, 6.1)


def test_parse_experiments():
    ex = parse_experiments(ROOT / "curated/laccase/experiments.csv")
    assert len(ex) == 8
    assert ex["pfoa-two-weeks"]["statistic"] == "p = 0.29 (two-tailed t test)"
    assert ex["cbz-positive-control"]["statistic"] == "p < 0.001 (two-tailed t test)"
    assert ex["screen-white-rot"]["replicates"] == 3


def test_record_set_and_validity(records):
    assert {r["slug"] for r in records} == {
        "acs-laccase-path", "acs-laccase-mediator-screen", "acs-laccase-system-checks",
        "acs-laccase-pfaa-degradation", "acs-laccase-sorption"}
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_pfoa_not_replicated_is_an_informative_negative(records):
    """Positive control is a different substrate in a separate reactor set with the same enzyme, mediator and buffer;
    negative control is the untreated reactor; sensitivity is the quantification range plus the expected effect."""
    f = finding(records, "acs-laccase-pfaa-degradation", "pfoa-two-weeks")
    assert f["outcomeClass"] == "negative-not-replicated" and f["informativeness"] == "informative"
    assert f["effect"]["pValue"] == 0.29 and f["effect"]["test"] == "two-tailed t test" and f["effect"]["significant"] is False
    assert f["controls"]["positive"]["kind"] == "designated" and f["controls"]["positive"]["passed"] is True
    assert "carbamazepine" in f["controls"]["positive"]["label"].lower()
    assert "separate" in f["controls"]["positive"]["note"]
    assert f["controls"]["negative"]["kind"] == "no-treatment" and f["controls"]["negative"]["passed"] is True
    assert "0.2" in f["sensitivity"] and "20" in f["sensitivity"]
    assert f["nearestPriorResult"].startswith("Luo et al. 2015")
    assert f["conditions"]["doses"] == 6 and f["conditions"]["enzymeUnitsPerMl"] == 1


def test_apparent_loss_is_refuted_by_mass_balance(records):
    f = finding(records, "acs-laccase-pfaa-degradation", "pfoa-96h-apparent-loss")
    assert f["outcomeClass"] == "refuted" and f["informativeness"] == "not-applicable"
    assert f["effect"]["value"] == 64 and f["effect"]["unit"] == "%"
    assert "99" in f["effect"]["comparedTo"] and "14" in f["effect"]["comparedTo"]
    assert f["failureModes"] == ["measurement-artifact"]
    g = finding(records, "acs-laccase-pfaa-degradation", "pfos-96h-apparent-loss")
    assert g["effect"]["value"] == 67 and "111" in g["effect"]["comparedTo"]
    assert "acs-laccase-sorption#pfos-partition" in g["relatedFindings"]


def test_the_screen_is_inconclusive_for_want_of_a_positive_control(records):
    f = finding(records, "acs-laccase-mediator-screen", "screen-white-rot")
    assert f["outcomeClass"] == "inconclusive-no-positive-control"
    assert f["informativenessReason"] == "no positive control"
    assert f["controls"]["negative"]["kind"] == "no-treatment" and f["controls"]["negative"]["passed"] is True
    assert f["effect"]["pValue"] == 0.58
    assert "evaporation" in f["controls"]["negative"]["note"]
    assert finding(records, "acs-laccase-mediator-screen", "screen-agaricus")["effect"]["pValue"] == 0.24
    scr = by_slug(records, "acs-laccase-mediator-screen")
    assert scr["outcomeClass"] == "inconclusive-no-positive-control"      # headline follows the remapped findings
    assert len(scr["screened"]) == 5 and all(s["type"] == "compound" for s in scr["screened"])


def test_system_checks_are_positive(records):
    cbz = finding(records, "acs-laccase-system-checks", "cbz-transformed")
    assert cbz["outcomeClass"] == "positive" and cbz["effect"]["value"] == 35 and cbz["effect"]["pValue"] == "< 0.001"
    epr = finding(records, "acs-laccase-system-checks", "btno-radical")
    assert epr["outcomeClass"] == "positive" and epr["conditions"]["g"] == 2.0069


def test_sorption_findings_carry_every_table_cell(records):
    f = finding(records, "acs-laccase-sorption", "pfos-partition")
    assert f["outcomeClass"] == "positive"
    assert f["effect"]["value"] == 34 and f["effect"]["sd"] == 3.5
    locs = [e["locator"] for e in f["evidence"]]
    assert len(locs) == 12 and all(l.startswith("SI Table S3") for l in locs)
    r = finding(records, "acs-laccase-sorption", "pfos-reactor-sorption")
    assert r["effect"]["value"] == 40 and "14" in r["effect"]["comparedTo"] and "12" in r["effect"]["comparedTo"]
    p = finding(records, "acs-laccase-sorption", "pfoa-partition")
    assert p["effect"]["value"] == 18 and p["conditions"]["tvlOnlyLossPct"] == 8


def test_path_contradicts_the_prior_reports(records):
    p = by_slug(records, "acs-laccase-path")
    assert p["outcomeClass"] == "negative-not-replicated"
    targets = {r["target"] for r in p["relations"] if r["type"] == "contradicts"}
    assert targets == {"doi:10.1021/acs.estlett.5b00119", "doi:10.1021/acs.est.8b00839"}
    roles = {s["identifier"]: s["role"] for s in p["sources"]}
    assert roles["doi:10.1021/acs.estlett.5b00119"] == "prior-art"
    ents = {e["label"]: e for e in p["entities"]}
    assert any(e["type"] == "organism" and e["id"].startswith("NCBITaxon:") for e in ents.values())
    assert any(e["type"] == "compound" and e["id"].startswith("pubchem:") and "PFOA" in e["label"] for e in ents.values())
    assert len(p["hasPart"]) == 4


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)
