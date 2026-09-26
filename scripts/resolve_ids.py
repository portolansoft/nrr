"""Populate curated/identifiers.json by querying public identifier services once.

Usage: uv run python scripts/resolve_ids.py   (network required)
Everything else in the pipeline runs offline against the resulting cache.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nrr.resolve import Resolver  # noqa: E402

wanted = yaml.safe_load((ROOT / "curated" / "identifiers_wanted.yaml").read_text())
r = Resolver(ROOT / "curated" / "identifiers.json", online=True, pause=0.6)
r.cache = {k: v for k, v in r.cache.items() if not (isinstance(v, dict) and "error" in v)}

# compounds: table 1 + extra table-5 labels + alcalase items
names = set(wanted.get("compounds", []))
with open(ROOT / "curated" / "robin" / "supp_table1_drugs.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        names.add(row["label"])
for n in sorted(names):
    print("compound", n, "->", (r.compound(n) or {}).get("identifier"))
for g in wanted.get("proteins", []):
    print("protein", g, "->", (r.protein(g) or {}).get("identifier"))
for term in wanted.get("ontology", []):
    print("ontology", term, "->", (r.ontology(term) or {}).get("identifier"))
for cl in wanted.get("cellLines", []):
    print("cellline", cl, "->", (r.cell_line(cl) or {}).get("identifier"))
for g in wanted.get("genes", []):
    print("gene", g, "->", (r.gene(g) or {}).get("identifier"))
for o in wanted.get("organizations", []):
    print("org", o, "->", (r.organization(o) or {}).get("identifier"))
for rr in wanted.get("rrids", []):
    print("rrid", rr, "->", (r.rrid(rr) or {}).get("label"))
# supplementary references have no DOIs in the PDF: resolve them from the citation text
sp = ROOT / "curated" / "robin" / "supplementary_references.json"
srefs = json.loads(sp.read_text())
for n, ref in srefs.items():
    if not ref.get("doi"):
        hit = r.citation_doi(ref["text"])
        if hit:
            ref["doi"] = hit["doi"]
            ref["doiResolvedBy"] = "crossref-bibliographic-query"
            ref["doiResolvedTitle"] = hit.get("title")
    print("supp ref", n, "->", ref.get("doi"))
sp.write_text(json.dumps(srefs, indent=1, ensure_ascii=False))
dois = set(wanted.get("dois", []))
for path in ["curated/robin/nature_references.json", "curated/robin/supplementary_references.json"]:
    p = ROOT / path
    if p.exists():
        for ref in json.loads(p.read_text()).values():
            if ref.get("doi"):
                dois.add(ref["doi"])
for d in sorted(dois):
    st = r.doi_status(d)
    print("doi", d, "->", st.get("version"), st.get("integrity"))
r.save()
print("misses:", r.misses)
print("cache entries:", len(r.cache))
