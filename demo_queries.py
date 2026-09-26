"""Ask the pilot store the questions an agent would ask. Usage: uv run python demo_queries.py [out/portolan.sqlite]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from nrr.db import query  # noqa: E402

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "portolan.sqlite"

QUESTIONS = [
    ("Has ripasudil been tested as an RPE phagocytosis enhancer, and what happened?", "prior_art", {"target": "ripasudil"}),
    ("Same question by PubChem identifier (CID 9863672)", "prior_art_by_identifier", {"identifier": "pubchem:CID9863672"}),
    ("What do we know about fingolimod in this assay, at what dose?", "negatives_for_target", {"target": "Fingolimod"}),
    ("Has Alcalase been used to deliver CRISPR reagents into cell-walled Chlamydomonas?", "search", {"text": "alcalase chlamydomonas"}),
    ("Which negatives in the store are NOT evidence of absence, and why?", "uninformative_negatives", {}),
    ("Which records concern Chlamydomonas reinhardtii (NCBITaxon:3055)?", "by_entity", {"entity_id": "NCBITaxon:3055"}),
    ("What did OpenAI Deep Research produce?", "by_performer", {"name": "Deep Research"}),
    ("Where could an agent pick up work (untried branches, open questions, deposited-but-unanalysed data)?", "open_branches", {}),
    ("Are the DOIs the Arcadia record depends on still intact?", "references_status", {"study_id": "arcadia-alcalase"}),
    ("Which records involved software agents and what did they cost?", "agents_and_cost", {}),
    ("Corpus overview by outcome class", "outcome_summary", {}),
]


def main() -> None:
    for q, name, params in QUESTIONS:
        rows = query(DB, name, **params)
        print(f"\n## {q}\n   query={name} params={params} -> {len(rows)} rows")
        for r in rows[:12]:
            r = {k: (v[:110] + "…" if isinstance(v, str) and len(v) > 110 else v) for k, v in r.items() if v not in (None, "", "[]")}
            print("   -", json.dumps(r, ensure_ascii=False))
        if len(rows) > 12:
            print(f"   … {len(rows) - 12} more")


if __name__ == "__main__":
    main()
