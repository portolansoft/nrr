"""Render each publishable path as a discourse graph page for the website.

Usage: uv run python scripts/render_graphs.py [--dest ../portolansoft/site/graphs] [--study arcadia-alcalase]
Writes <dest>/<study>.html for every study whose records are published, plus <dest>/index.html. Offline and
deterministic. Only the studies `export_records.py` publishes are rendered; the Nature-derived study is not, because
its source licence (CC BY-NC-ND 4.0) forbids distributing adapted material and node titles would be exactly that.

    uv run python scripts/render_graphs.py --restricted robin-damd --dest ../portolansoft/site/graphs/robin

renders the Nature-derived study to <dest>/index.html for a page the website serves only behind a login, to named
reviewers. It is not publication: no record links (the records are not published), a noindex tag, no sitemap entry.
Whether showing it to anyone at all is within the licence is a judgement the site owner makes, not this script.
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
        "published: its licence is CC BY-NC-ND 4.0 and a graph of its records would be adapted material. A rendering of it "
        "exists for named reviewers, behind a login and not indexed. Eight open-access SAGE papers, drawn from their full "
        "text rather than from records, are at <a href=\"/graphs/sage/\">/graphs/sage/</a>, and seven CC BY papers on "
        "physics-informed neural networks at <a href=\"/graphs/pinns-karniadakis/\">/graphs/pinns-karniadakis/</a>, and eleven CC BY "
        "ACM papers, positive and negative, at <a href=\"/graphs/acm/\">/graphs/acm/</a>.")
RESTRICTED = {"robin-damd": {
    "url": "/graphs/robin/",
    "notice": (" This page is shown to named reviewers only. The source is CC BY-NC-ND 4.0, so the records it is drawn from "
               "are not published and nothing here links to one; please do not copy or redistribute it."),
}}
HEAD_NOINDEX = '<meta name="robots" content="noindex, nofollow">\n'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT.parent / "portolansoft" / "site" / "graphs"))
    ap.add_argument("--study", choices=sorted(BUILDERS))
    ap.add_argument("--restricted", choices=sorted(RESTRICTED), help="render one unpublishable study to <dest>/index.html")
    a = ap.parse_args()
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    resolver = Resolver(ROOT / "curated" / "identifiers.json", online=False)
    if a.restricted:
        return render_restricted(a.restricted, dest, resolver)
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


def render_restricted(study: str, dest: Path, resolver: Resolver) -> int:
    if study == "robin-damd":
        if not (ROOT / "raw" / "robin" / "robin_output").exists():
            print("raw/robin is missing; run scripts/fetch_sources.py --study robin-damd first", file=sys.stderr)
            return 1
        from nrr.ingest.robin import build_robin_records
        records = build_robin_records(ROOT, resolver)
    else:  # pragma: no cover
        raise SystemExit(f"no restricted builder for {study}")
    for rec in records:
        problems = validate(rec)
        if problems:
            print(f"{rec['slug']}: {problems}", file=sys.stderr)
            return 1
    path = next(r for r in records if r["kind"] == "path")
    attempts = [r for r in records if r["kind"] == "attempt"]
    g = build_graph(path, attempts, record_base=None)
    spec = RESTRICTED[study]
    (dest / "index.html").write_text(render_page(g, url=spec["url"], notice=spec["notice"], head_extra=HEAD_NOINDEX), encoding="utf-8")
    print(f"{study} (restricted, {spec['url']}): {sum(1 for n in g['nodes'] if n['kind'] == 'EXP')} attempts, "
          f"{sum(1 for n in g['nodes'] if n['kind'] == 'RES')} findings, {len(g['edges'])} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
