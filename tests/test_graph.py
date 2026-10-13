"""Rendering a path as a discourse graph: question, hypothesis, attempts, findings, issues.

The graph is a view over existing fields. Nothing here may change a record, and the output must be deterministic.
"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from nrr.graph import build_graph, render_page, render_svg, valence

RECORD_BASE = "https://github.com/portolansoft/nrr-records/blob/main"
from nrr.ingest.alcalase import build_alcalase_records
from nrr.resolve import Resolver

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def alcalase():
    resolver = Resolver(ROOT / "curated" / "identifiers.json", online=False)
    records = build_alcalase_records(ROOT, resolver)
    path = next(r for r in records if r["kind"] == "path")
    attempts = [r for r in records if r["kind"] == "attempt"]
    return path, attempts


# --- valence: the edge a finding earns against the hypothesis -------------------------------------------------------

@pytest.mark.parametrize("outcome,informativeness,expected", [
    ("positive", "not-applicable", "supports"),
    ("partial", "not-applicable", "informs"),
    ("refuted", "not-applicable", "opposes"),
    ("negative-no-effect", "informative", "opposes"),
    ("negative-not-achievable", "informative", "opposes"),
    ("negative-not-replicated", "informative", "opposes"),
    # the informativeness rule decides the edge: an uninformative negative is only consistent with the hypothesis
    ("negative-no-effect", "uninformative", "consistent-with"),
    ("inconclusive-no-positive-control", "uninformative", "consistent-with"),
    ("inconclusive-controls-failed", "uninformative", "consistent-with"),
    ("inconclusive", "uninformative", "consistent-with"),
])
def test_valence(outcome, informativeness, expected):
    assert valence({"outcomeClass": outcome, "informativeness": informativeness}) == expected


# --- graph structure ----------------------------------------------------------------------------------------------

def test_graph_has_one_node_per_question_hypothesis_attempt_and_finding(alcalase):
    path, attempts = alcalase
    g = build_graph(path, attempts, record_base=RECORD_BASE)
    kinds = [n["kind"] for n in g["nodes"]]
    assert kinds.count("QUE") == 1 and kinds.count("HYP") == 1
    assert kinds.count("EXP") == len(attempts) == 6
    assert kinds.count("RES") == sum(len(a["findings"]) for a in attempts) == 11
    # issues: open questions plus untried branches; next steps that duplicate an untried branch are not repeated
    iss = [n for n in g["nodes"] if n["kind"] == "ISS"]
    assert len(iss) == len(path["openQuestions"]) + len(path["untriedBranches"])
    assert g["studyId"] == "arcadia-alcalase"


def test_graph_edges_follow_the_grammar(alcalase):
    path, attempts = alcalase
    g = build_graph(path, attempts, record_base=RECORD_BASE)
    by_id = {n["id"]: n for n in g["nodes"]}
    labels = {}
    for e in g["edges"]:
        labels.setdefault((by_id[e["source"]]["kind"], by_id[e["target"]]["kind"]), set()).add(e["label"])
    assert labels[("QUE", "EXP")] == {"addresses"}
    assert labels[("EXP", "RES")] == {"produces"}
    assert labels[("RES", "HYP")] <= {"supports", "opposes", "informs", "consistent-with"}
    # every finding bears on the hypothesis exactly once
    res_to_hyp = [e for e in g["edges"] if by_id[e["source"]]["kind"] == "RES" and by_id[e["target"]]["kind"] == "HYP"]
    assert len(res_to_hyp) == 11
    # the record's own relations between attempts survive (alcalase has one wasDerivedFrom)
    assert ("EXP", "EXP") in labels and "wasDerivedFrom" in labels[("EXP", "EXP")]


def test_finding_node_carries_what_the_reader_needs(alcalase):
    path, attempts = alcalase
    g = build_graph(path, attempts, record_base=RECORD_BASE)
    hdr = next(n for n in g["nodes"] if n["kind"] == "RES" and n["outcomeClass"] == "inconclusive-no-positive-control")
    assert hdr["informativeness"] == "uninformative"
    assert hdr["informativenessReason"]
    assert hdr["valence"] == "consistent-with"
    assert hdr["record"].endswith("arcadia-alcalase-hdr-knockin.json")


# --- rendering -----------------------------------------------------------------------------------------------------

def test_svg_is_well_formed_and_has_every_node(alcalase):
    path, attempts = alcalase
    g = build_graph(path, attempts, record_base=RECORD_BASE)
    svg = render_svg(g)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    ids = {el.get("id") for el in root.iter() if el.get("id")}
    for n in g["nodes"]:
        assert "n-" + n["id"] in ids, n["id"]
    assert "<script" not in svg and "style=" not in svg  # the site's CSP forbids inline script and style


def test_page_is_deterministic_and_links_records(alcalase):
    path, attempts = alcalase
    g = build_graph(path, attempts, record_base=RECORD_BASE)
    a, b = render_page(g), render_page(g)
    assert a == b
    assert "https://github.com/portolansoft/nrr-records/blob/main/arcadia-alcalase/records/arcadia-alcalase-hdr-knockin.json" in a
    assert "<title>" in a and "Alcalase" in a
    assert "<script" not in a.split("<body>")[1].split("<footer")[0]  # body carries no inline script


def test_script_renders_eight_pages_and_never_robin(tmp_path):
    out = tmp_path / "graphs"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "render_graphs.py"), "--dest", str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-2000:]
    pages = sorted(p.name for p in out.glob("*.html"))
    assert pages == ["acs-laccase.html", "acs-tmeda.html", "acs-xef6.html", "acs-zeolite.html", "arcadia-alcalase.html",
                     "arcadia-dfa.html", "arcadia-neuroimaging.html", "arcadia-raman.html", "index.html"]
    assert not any("robin" in p.read_text() for p in out.glob("*.html") if p.name != "index.html")
