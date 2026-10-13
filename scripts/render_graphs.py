"""Render each publishable path as a discourse graph page for the website.

Usage: uv run python scripts/render_graphs.py [--dest ../portolansoft/site/graphs] [--study arcadia-alcalase]
Writes <dest>/<study>.html for every study whose records are published, plus <dest>/index.html. Offline and
deterministic. Only the studies `export_records.py` publishes are rendered; the Nature-derived study is not, because
its source licence (CC BY-NC-ND 4.0) forbids distributing adapted material and node titles would be exactly that.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from export_records import BUILDERS  # noqa: E402  the open node's publishing list is the licence gate
from nrr.graph import build_graph, render_index, render_page  # noqa: E402
from nrr.resolve import Resolver  # noqa: E402
from nrr.schema import validate  # noqa: E402

RECORD_BASE = "https://github.com/portolansoft/nrr-records/blob/main"
NOTE = ("Eight of the nine pilot studies are drawn here. The ninth, Ghareeb et al. 2026 in Nature, is encoded but not "
        "published: its licence is CC BY-NC-ND 4.0 and a graph of its records would be adapted material.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT.parent / "portolansoft" / "site" / "graphs"))
    ap.add_argument("--study", choices=sorted(BUILDERS))
    a = ap.parse_args()
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    resolver = Resolver(ROOT / "curated" / "identifiers.json", online=False)
    graphs = []
    for study in sorted(BUILDERS):
        if a.study and study != a.study:
            continue
        records = BUILDERS[study](ROOT, resolver)
        for rec in records:
            problems = validate(rec)
            if problems:
                print(f"{rec['slug']}: {problems}", file=sys.stderr)
                return 1
        path = next(r for r in records if r["kind"] == "path")
        attempts = [r for r in records if r["kind"] == "attempt"]
        g = build_graph(path, attempts, record_base=RECORD_BASE)
        (dest / f"{study}.html").write_text(render_page(g), encoding="utf-8")
        graphs.append(g)
        print(f"{study}: {sum(1 for n in g['nodes'] if n['kind'] == 'EXP')} attempts, "
              f"{sum(1 for n in g['nodes'] if n['kind'] == 'RES')} findings, {len(g['edges'])} edges")
    if not a.study:
        (dest / "index.html").write_text(render_index(graphs, note=NOTE), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
