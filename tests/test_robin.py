"""Facts pinned from Ghareeb et al. 2026 and the Robin repository; the converter must reproduce them."""
from pathlib import Path

import pytest

from nrr.ingest.robin import (
    bradley_terry,
    build_robin_records,
    parse_ena_runs,
    parse_pairwise_csv,
    parse_ranked_csv,
    parse_references,
    parse_supp_table,
)
from nrr.resolve import Resolver
from nrr.schema import validate

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "raw" / "robin" / "robin_output").exists(), reason="raw/robin not fetched (scripts/fetch_sources.py --study robin-damd)")
RUN1 = ROOT / "raw/robin/robin_output/dry_age-related_macular_degeneration_2025-05-28_16-51"


@pytest.fixture(scope="module")
def resolver():
    return Resolver(ROOT / "curated/identifiers.json", online=False)


@pytest.fixture(scope="module")
def records(resolver):
    return build_robin_records(ROOT, resolver)


def by_slug(records, slug):
    return next(r for r in records if r["slug"] == slug)


# ---- parsers ----------------------------------------------------------------------------

def test_parse_ranked_csv_reads_scores_and_names():
    rows = parse_ranked_csv(RUN1 / "ranked_therapeutic_candidates_experimental.csv")
    assert len(rows) == 30
    assert rows[0]["name"].startswith("Rapamycin")
    assert rows[0]["strength_score"] == pytest.approx(1.223, abs=1e-3)
    assert rows[0]["rank"] == 1


def test_parse_pairwise_csv_and_bradley_terry_rank_phagocytosis_first():
    pairs, names = parse_pairwise_csv(RUN1 / "experimental_assay_ranking_results.csv")
    assert len(pairs) == 45
    scores = bradley_terry(pairs, len(names))
    best = max(range(len(names)), key=lambda i: scores[i])
    assert names[best] == "Phagocytosis assay"


def test_parse_supp_table_aggregates_per_drug():
    table = parse_supp_table(ROOT / "raw/robin/supplementary/41586_2026_10652_MOESM3_ESM.xlsx", "Supp Table 4")
    rip = table["Ripasudil"]
    assert rip["n"] == 3
    assert rip["mean"] == pytest.approx(1.891, abs=1e-3)
    assert set(rip["plates"]) == {"250403_RPEassay plate1", "250403_RPEassay plate2", "250403_RPEassay plate3"}


def test_parse_ena_runs():
    runs = parse_ena_runs(ROOT / "raw/robin/sra/ena_read_run_PRJNA1464762.tsv")
    assert len(runs) == 29
    assert all(r["run_accession"].startswith("SRR") for r in runs)
    conditions = {r["condition"] for r in runs}
    assert {"Y27632", "exendin4", "MLN120B", "AT", "wildtype"} <= conditions


def test_parse_references_extracts_dois_from_crow_and_falcon_files():
    crow = parse_references(RUN1 / "experimental_assay_detailed_hypotheses/assay_hypothesis_10_phagocytosis.txt")
    assert any(r["doi"] == "10.1186/s12967-018-1434-6" for r in crow)
    falcon = parse_references(RUN1 / "therapeutic_candidate_detailed_hypotheses/therapeutic_candidate_1_pegcetacoplan.txt")
    assert any(r["doi"] == "10.1002/14651858.cd009300.pub3" for r in falcon)


# ---- records ----------------------------------------------------------------------------

def test_record_set_and_validity(records):
    slugs = {r["slug"] for r in records}
    assert slugs == {
        "robin-damd-path", "robin-damd-assay-selection", "robin-damd-candidates-r1", "robin-damd-screen-r1-arpe19",
        "robin-damd-finch-flow-r1", "robin-damd-candidates-r2", "robin-damd-screen-r2-arpe19", "robin-damd-rnaseq-arpe19",
        "robin-damd-screen-rpesc", "deep-research-damd-candidates", "robin-ablation-reference-check",
    }
    for r in records:
        assert validate(r) == [], (r["slug"], validate(r)[:3])


def test_ripasudil_is_a_hit_in_round_two(records):
    r2 = by_slug(records, "robin-damd-screen-r2-arpe19")
    f = next(f for f in r2["findings"] if f["target"]["label"] == "Ripasudil")
    assert f["outcomeClass"] == "positive"
    assert f["effect"]["value"] == pytest.approx(1.891, abs=1e-3)
    assert f["effect"]["n"] == 3
    assert f["conditions"]["dose"] == "100 µM"
    assert f["target"]["identifier"] == "pubchem:CID9863672"


def test_kl001_negative_in_arpe19_positive_in_rpesc(records):
    r2 = by_slug(records, "robin-damd-screen-r2-arpe19")
    sc = by_slug(records, "robin-damd-screen-rpesc")
    kl_r2 = next(f for f in r2["findings"] if f["target"]["label"] == "KL001")
    kl_sc = next(f for f in sc["findings"] if f["target"]["label"] == "KL001")
    assert kl_r2["outcomeClass"] == "negative-no-effect"
    assert kl_sc["outcomeClass"] == "positive"
    assert kl_r2["informativeness"] == "informative"


def test_round_one_negatives_are_informative_via_designated_control(records):
    r1 = by_slug(records, "robin-damd-screen-r1-arpe19")
    fin = next(f for f in r1["findings"] if f["target"]["label"] == "Fingolimod")
    assert fin["outcomeClass"] == "negative-no-effect"
    assert fin["informativeness"] == "informative"
    assert fin["controls"]["positive"]["label"] == "MFGE8" and fin["controls"]["positive"]["passed"]


def test_finch_round_one_reports_control_discrepancy(records):
    fx = by_slug(records, "robin-damd-finch-flow-r1")
    assert fx["attemptType"] == "computational"
    ctrl = next(f for f in fx["findings"] if f["target"]["label"] == "MFGE8")
    assert ctrl["outcomeClass"] == "negative-no-effect"          # Finch did not separate the control from vehicle
    assert ctrl["informativeness"] == "informative" and "internal" in ctrl["informativenessReason"]
    tudca = next(f for f in fx["findings"] if f["target"]["label"] == "TUDCA")
    assert tudca["outcomeClass"] == "inconclusive-controls-failed"  # other negatives inherit the failed control
    assert any("human analysis" in n.lower() for n in fx["provenanceNotes"])
    assert any(p["model"].startswith("anthropic/claude-3-7-sonnet") for p in fx["performers"] if p.get("model"))


def test_repo_candidates_are_deferred_with_provenance_note(records):
    c1 = by_slug(records, "robin-damd-candidates-r1")
    deferred = [s for s in c1["screened"] if s["decision"] == "deferred"]
    included = [s for s in c1["screened"] if s["decision"] == "included"]
    assert len(deferred) == 59
    assert {s["label"] for s in included} == {"Y-27632", "AICAR + TUDCA", "Exendin-4", "Fingolimod", "MFGE8"}
    assert any("re-run" in n for n in c1["provenanceNotes"])
    assert all(s["score"]["method"].startswith("bradley-terry") for s in deferred)


def test_deep_research_arm_has_no_hits(records):
    dr = by_slug(records, "deep-research-damd-candidates")
    assert dr["outcomeClass"].startswith("negative")
    assert dr["performers"][0]["name"] == "Deep Research"
    assert sum(1 for s in dr["screened"]) == 15
    assert all(f["outcomeClass"] == "negative-no-effect" for f in dr["findings"])


def test_rnaseq_record_points_at_sra_and_unanalysed_branches(records):
    rna = by_slug(records, "robin-damd-rnaseq-arpe19")
    ptrs = [d for s in rna["sources"] if s["role"] == "data-deposit" for d in s.get("data", [])]
    assert len(ptrs) == 29
    assert all(p["checksum"].startswith("md5:") for p in ptrs)
    abca1 = next(f for f in rna["findings"] if f["target"]["label"] == "ABCA1")
    assert abca1["target"]["identifier"] == "HGNC:29"
    branches = " ".join(b["description"] for b in rna["untriedBranches"])
    assert "exendin" in branches.lower() and "MLN120B" in branches and "AT" in branches
    assert any(b["status"] == "data-deposited-not-analysed" for b in rna["untriedBranches"])


def test_path_links_all_attempts(records):
    path = by_slug(records, "robin-damd-path")
    ids = {r["@id"] for r in records if r["kind"] == "attempt"}
    assert set(path["hasPart"]) == ids
    for r in records:
        if r["kind"] == "attempt":
            assert r["isPartOf"] == path["@id"]


def test_ids_are_content_addresses(records):
    from nrr.identity import content_address
    for r in records:
        assert r["@id"] == content_address(r)


def test_bradley_terry_handles_empty_input():
    assert bradley_terry([], 0) == []
