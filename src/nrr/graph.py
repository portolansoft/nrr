"""Render a path and its attempts as a discourse graph.

A view over existing record fields, in the grammar of Discourse Graphs (Chan and Akamatsu; discoursegraphs.com):
QUE question, HYP hypothesis, EXP experiment, RES result, ISS issue; edges addresses, produces, supports, opposes,
informs, consistent-with. Nothing here reads anything a record does not already say, and nothing here writes to a
record. Output is deterministic: no clock, no randomness, no network.

The one judgement this module makes is `valence`: which edge a finding earns against the path hypothesis. It is
derived from `outcomeClass` and `informativeness`, so the informativeness rule decides whether a negative is drawn as
opposing the hypothesis or merely consistent with it.
"""
from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

KINDS = {"QUE": "Question", "HYP": "Hypothesis", "EXP": "Experiment", "RES": "Result", "ISS": "Issue"}


# --- valence -----------------------------------------------------------------------------------------------------

def valence(finding: dict) -> str:
    """The edge a finding earns against the hypothesis it bears on.

    An uninformative or inconclusive finding is only `consistent-with`: it neither supports nor opposes, which is what
    the informativeness rule means. Positives support, partials inform, refutations and informative negatives oppose.
    """
    oc = finding["outcomeClass"]
    if finding.get("informativeness") == "uninformative" or oc.startswith("inconclusive"):
        return "consistent-with"
    if oc == "positive":
        return "supports"
    if oc in ("partial", "abandoned"):
        return "informs"
    if oc == "refuted" or oc.startswith("negative"):
        return "opposes"
    return "informs"


# --- graph ---------------------------------------------------------------------------------------------------------

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _effect_text(f: dict) -> str:
    e = f.get("effect") or {}
    if not e.get("metric"):
        return ""
    parts = [e["metric"]]
    if e.get("value") is not None:
        v = e["value"]
        parts.append(f"= {v}{(' ' + e['unit']) if e.get('unit') else ''}")
    if e.get("n") is not None:
        parts.append(f"(n = {e['n']})")
    return " ".join(parts)


def build_graph(path: dict, attempts: list[dict], record_base: str | None = None) -> dict:
    """Nodes and edges for one path. `record_base` is where the caller publishes record JSON; None means no links."""
    study = path["studyId"]
    attempts = sorted(attempts, key=lambda a: a["slug"])

    def record_url(slug: str) -> str | None:
        return f"{record_base}/{study}/records/{slug}.json" if record_base else None

    nodes: list[dict] = []
    edges: list[dict] = []
    nodes.append({"id": "que", "kind": "QUE", "label": path["question"], "record": record_url(path["slug"]),
                  "slug": path["slug"], "outcomeClass": path["outcomeClass"], "outcomeSummary": path.get("outcomeSummary")})
    nodes.append({"id": "hyp", "kind": "HYP", "label": path.get("hypothesis") or path.get("successCriteria") or path["title"],
                  "record": record_url(path["slug"]), "slug": path["slug"],
                  "note": None if path.get("hypothesis") else "The record states no hypothesis; its success criteria stand in."})

    id_to_slug = {a["@id"]: a["slug"] for a in attempts}
    for a in attempts:
        exp = {"id": a["slug"], "kind": "EXP", "label": a["title"], "attemptType": a.get("attemptType"),
               "outcomeClass": a["outcomeClass"], "outcomeSummary": a.get("outcomeSummary"),
               "record": record_url(a["slug"]), "slug": a["slug"], "findings": []}
        nodes.append(exp)
        edges.append({"source": "que", "target": a["slug"], "label": "addresses"})
        for f in a.get("findings") or []:
            fid = f"{a['slug']}--{_slug(f['id'])}"
            v = valence(f)
            exp["findings"].append(fid)
            nodes.append({"id": fid, "kind": "RES", "label": f["question"], "findingId": f["id"], "attempt": a["slug"],
                          "outcomeClass": f["outcomeClass"], "informativeness": f["informativeness"],
                          "informativenessReason": f.get("informativenessReason"), "effect": _effect_text(f),
                          "target": (f.get("target") or {}).get("label"), "valence": v,
                          "record": record_url(a["slug"]), "slug": a["slug"]})
            edges.append({"source": a["slug"], "target": fid, "label": "produces"})
            edges.append({"source": fid, "target": "hyp", "label": v})
    for a in attempts:
        for rel in a.get("relations") or []:
            if rel["type"] == "isPartOf":
                continue
            tgt = id_to_slug.get(rel["target"])
            if tgt and tgt != a["slug"]:
                edges.append({"source": a["slug"], "target": tgt, "label": rel["type"], "note": rel.get("note")})

    # issues: open questions and untried branches; next steps are usually already untried branches, so only add the rest
    branch_texts = {b["description"] for b in path.get("untriedBranches") or []}
    n = 0
    for q in path.get("openQuestions") or []:
        n += 1
        nodes.append({"id": f"iss-{n}", "kind": "ISS", "label": q, "status": "open-question", "record": record_url(path["slug"]), "slug": path["slug"]})
    for b in path.get("untriedBranches") or []:
        n += 1
        nodes.append({"id": f"iss-{n}", "kind": "ISS", "label": b["description"], "status": b["status"], "source": b.get("source"),
                      "record": record_url(path["slug"]), "slug": path["slug"]})
    for s in path.get("nextSteps") or []:
        if s not in branch_texts:
            n += 1
            nodes.append({"id": f"iss-{n}", "kind": "ISS", "label": s, "status": "next-step", "record": record_url(path["slug"]), "slug": path["slug"]})

    src_pub = next((s for s in path.get("sources") or [] if s.get("role") == "source-publication"), {})
    return {"studyId": study, "title": path["title"], "slug": path["slug"], "outcomeClass": path["outcomeClass"],
            "outcomeSummary": path.get("outcomeSummary"), "abandonmentReasons": path.get("abandonmentReasons") or [],
            "sourcePublication": {"identifier": src_pub.get("identifier"), "label": src_pub.get("label"), "url": src_pub.get("url"), "license": src_pub.get("license")},
            "profile": path.get("profile"), "version": path.get("version"), "nodes": nodes, "edges": edges}


# --- layout and SVG --------------------------------------------------------------------------------------------------

W = 260            # node width
COL_X = {"QUE": 0, "EXP": 340, "RES": 680, "HYP": 1020}
LINE = 15          # text line height
HEAD = 24          # kind row
PAD = 10
GAP = 10           # between results of one attempt
BLOCK_GAP = 28     # between attempts
ISS_GAP = 44       # between the graph and the issues strip
CHARS = 40         # characters per line at 12px


def _wrap(text: str, max_lines: int) -> list[str]:
    lines = textwrap.wrap(text, CHARS) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: CHARS - 1].rstrip(" ,;:") + "…"
    return lines


def _node_h(lines: int) -> int:
    return HEAD + lines * LINE + PAD


def layout(graph: dict) -> dict:
    """Positions for every node. Pure function of the graph."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    pos: dict[str, dict] = {}
    y = 0
    for exp in (n for n in graph["nodes"] if n["kind"] == "EXP"):
        exp_lines = _wrap(exp["label"], 4)
        exp_h = _node_h(len(exp_lines))
        res = [(fid, _wrap(by_id[fid]["label"], 3)) for fid in exp["findings"]]
        res_h = sum(_node_h(len(l)) for _, l in res) + GAP * max(0, len(res) - 1)
        block = max(exp_h, res_h)
        pos[exp["id"]] = {"x": COL_X["EXP"], "y": y + (block - exp_h) / 2, "w": W, "h": exp_h, "lines": exp_lines}
        ry = y + (block - res_h) / 2
        for fid, lines in res:
            h = _node_h(len(lines))
            pos[fid] = {"x": COL_X["RES"], "y": ry, "w": W, "h": h, "lines": lines}
            ry += h + GAP
        y += block + BLOCK_GAP
    total = max(y - BLOCK_GAP, 0)
    for nid in ("que", "hyp"):
        lines = _wrap(by_id[nid]["label"], 8)
        h = _node_h(len(lines))
        total = max(total, h)
        pos[nid] = {"x": COL_X[by_id[nid]["kind"]], "y": 0, "w": W, "h": h, "lines": lines}
    for nid in ("que", "hyp"):
        pos[nid]["y"] = (total - pos[nid]["h"]) / 2
    # issues: a strip under the graph, four to a row in the same four columns
    issues = [n for n in graph["nodes"] if n["kind"] == "ISS"]
    strip_y = total + ISS_GAP if issues else total
    cols = list(COL_X.values())
    y = strip_y
    for row_start in range(0, len(issues), len(cols)):
        row = issues[row_start:row_start + len(cols)]
        wrapped = [_wrap(n["label"], 4) for n in row]
        row_h = max(_node_h(len(l)) for l in wrapped)
        for (n, lines), x in zip(zip(row, wrapped), cols):
            pos[n["id"]] = {"x": x, "y": y, "w": W, "h": row_h, "lines": lines}
        y += row_h + GAP
    height = (y - GAP) if issues else total
    return {"pos": pos, "width": COL_X["HYP"] + W, "height": height, "strip_y": strip_y if issues else None}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_svg(graph: dict) -> str:
    lay = layout(graph)
    pos, width, height = lay["pos"], lay["width"], lay["height"]
    m = 8
    out = [f'<svg class="dg" xmlns="http://www.w3.org/2000/svg" viewBox="{-m} {-m} {width + 2 * m} {height + 2 * m}" '
           f'width="{width + 2 * m}" height="{height + 2 * m}" role="img" aria-labelledby="dg-title">',
           f'<title id="dg-title">Discourse graph of {_esc(graph["title"])}</title>', "<defs>"]
    for v in ("addresses", "produces", "supports", "opposes", "informs", "consistent-with", "relation"):
        out.append(f'<marker id="arrow-{v}" class="dg-arrow dg-arrow--{v}" viewBox="0 0 10 10" refX="9" refY="5" '
                   f'markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker>')
    out.append("</defs>")
    # edges first so nodes sit on top
    for e in graph["edges"]:
        s, t = pos[e["source"]], pos[e["target"]]
        label = e["label"]
        cls = label if label in ("addresses", "produces", "supports", "opposes", "informs", "consistent-with") else "relation"
        if s["x"] == t["x"]:  # same column: bow to the left
            x = s["x"]
            y1, y2 = s["y"] + s["h"] / 2, t["y"] + t["h"] / 2
            cx = x - 70
            d = f"M{x:.1f} {y1:.1f} C{cx:.1f} {y1:.1f} {cx:.1f} {y2:.1f} {x:.1f} {y2:.1f}"
        else:
            x1, y1 = s["x"] + s["w"], s["y"] + s["h"] / 2
            x2, y2 = t["x"], t["y"] + t["h"] / 2
            cx = (x1 + x2) / 2
            d = f"M{x1:.1f} {y1:.1f} C{cx:.1f} {y1:.1f} {cx:.1f} {y2:.1f} {x2:.1f} {y2:.1f}"
        title = f"{e['source']} {label} {e['target']}" + (f": {e['note']}" if e.get("note") else "")
        out.append(f'<path class="dg-edge dg-edge--{cls}" d="{d}" marker-end="url(#arrow-{cls})"><title>{_esc(title)}</title></path>')
    if lay.get("strip_y") is not None:
        out.append(f'<text class="dg-strip-head" x="0" y="{lay["strip_y"] - 14:.1f}">ISS · open questions and untried branches this path leaves behind</text>')
    for n in graph["nodes"]:
        p = pos[n["id"]]
        kind = n["kind"]
        head = kind
        if kind == "EXP":
            head = f"EXP · {n['outcomeClass']}"
        elif kind == "RES":
            head = f"RES · {n['outcomeClass']}"
        elif kind == "QUE":
            head = f"QUE · {n['outcomeClass']}"
        elif kind == "HYP":
            head = "HYP"
        elif kind == "ISS":
            head = f"ISS · {n['status']}"
        extra = " dg-node--uninformative" if n.get("informativeness") == "uninformative" else ""
        out.append(f'<a href="#{_esc(n["id"])}" class="dg-node dg-node--{kind.lower()}{extra}" id="n-{_esc(n["id"])}">')
        out.append(f'<rect x="{p["x"]}" y="{p["y"]:.1f}" width="{p["w"]}" height="{p["h"]}" rx="3"/>')
        out.append(f'<text class="dg-head" x="{p["x"] + PAD}" y="{p["y"] + 15:.1f}">{_esc(head)}</text>')
        for i, line in enumerate(p["lines"]):
            out.append(f'<text class="dg-label" x="{p["x"] + PAD}" y="{p["y"] + HEAD + 10 + i * LINE:.1f}">{_esc(line)}</text>')
        out.append(f"<title>{_esc(n['label'])}</title></a>")
    out.append("</svg>")
    return "\n".join(out)


# --- page ----------------------------------------------------------------------------------------------------------

def _load_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _link(url: str | None, text: str) -> str:
    return f'<a href="{_esc(url)}">{_esc(text)}</a>' if url else _esc(text)


def _node_row(n: dict) -> str:
    kind = n["kind"]
    cells = [f'<th scope="row" id="{_esc(n["id"])}"><span class="dg-tag dg-tag--{kind.lower()}">{kind}</span></th>']
    if kind == "EXP":
        cells.append(f"<td>{_esc(n['label'])}" + (f"<br><small>{_esc(n['outcomeSummary'])}</small>" if n.get("outcomeSummary") else "") + "</td>")
        cells.append(f"<td><code>{_esc(n.get('attemptType') or '')}</code></td>")
        cells.append(f"<td><code>{_esc(n['outcomeClass'])}</code></td>")
        cells.append("<td></td>")
    elif kind == "RES":
        extra = []
        if n.get("target"):
            extra.append(f"target: {n['target']}")
        if n.get("effect"):
            extra.append(n["effect"])
        cells.append(f"<td>{_esc(n['label'])}" + (f"<br><small>{_esc('; '.join(extra))}</small>" if extra else "") + "</td>")
        cells.append(f"<td><code>{_esc(n['findingId'])}</code><br><small>in {_esc(n['attempt'])}</small></td>")
        info = n["informativeness"]
        reason = f"<br><small>{_esc(n['informativenessReason'])}</small>" if n.get("informativenessReason") else ""
        cells.append(f"<td><code>{_esc(n['outcomeClass'])}</code><br><small>{_esc(info)}</small>{reason}</td>")
        cells.append(f'<td><span class="dg-edge-tag dg-edge-tag--{n["valence"]}">{_esc(n["valence"])}</span> HYP</td>')
    cells.append(f"<td>{_link(n['record'], 'record') if n.get('record') else 'withheld'}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def render_page(graph: dict, url: str | None = None, notice: str = "", head_extra: str = "") -> str:
    """`url` is the page's path on the site (default /graphs/<studyId>). `notice` is HTML appended to the meta line,
    and `head_extra` is HTML added to <head>; both exist so a restricted rendering can say so and ask not to be indexed."""
    tpl = _load_template("graph-page.html")
    nodes = graph["nodes"]
    que = next(n for n in nodes if n["kind"] == "QUE")
    hyp = next(n for n in nodes if n["kind"] == "HYP")
    exps = [n for n in nodes if n["kind"] == "EXP"]
    ress = [n for n in nodes if n["kind"] == "RES"]
    isss = [n for n in nodes if n["kind"] == "ISS"]
    counts = {v: sum(1 for r in ress if r["valence"] == v) for v in ("supports", "opposes", "informs", "consistent-with")}

    exp_rows = "\n".join(_node_row(n) for n in exps)
    res_rows = "\n".join(_node_row(n) for exp in exps for n in ress if n["attempt"] == exp["id"])
    iss_items = "\n".join(
        f'<li id="{_esc(n["id"])}"><span class="dg-tag dg-tag--iss">ISS</span> {_esc(n["label"])} <small>({_esc(n["status"])})</small></li>'
        for n in isss)
    relations = [e for e in graph["edges"] if e["label"] not in ("addresses", "produces", "supports", "opposes", "informs", "consistent-with")]
    rel_items = "\n".join(f"<li><code>{_esc(e['source'])}</code> {_esc(e['label'])} <code>{_esc(e['target'])}</code>" +
                          (f" <small>{_esc(e['note'])}</small>" if e.get("note") else "") + "</li>" for e in relations)
    sp = graph["sourcePublication"]
    src_html = _link(sp.get("url"), sp.get("label") or sp.get("identifier") or "source") + (f" <small>({_esc(sp['identifier'])})</small>" if sp.get("identifier") else "")
    hyp_note = f"<p><small>{_esc(hyp['note'])}</small></p>" if hyp.get("note") else ""
    abandon = f" Abandonment reasons: {', '.join(graph['abandonmentReasons'])}." if graph["abandonmentReasons"] else ""

    fill = {
        "title": _esc(graph["title"]),
        "study": _esc(graph["studyId"]),
        "description": _esc(f"{graph['title']}: the path question, hypothesis, {len(exps)} attempts and {len(ress)} findings drawn as a discourse graph, "
                            f"with the edge each finding earns under the informativeness rule."),
        "question": _esc(que["label"]),
        "hypothesis": _esc(hyp["label"]),
        "hyp_note": hyp_note,
        "outcome": _esc(graph["outcomeClass"]),
        "outcome_summary": _esc(graph.get("outcomeSummary") or "") + _esc(abandon),
        "source": src_html,
        "svg": render_svg(graph),
        "n_exp": str(len(exps)), "n_res": str(len(ress)), "n_iss": str(len(isss)),
        "n_supports": str(counts["supports"]), "n_opposes": str(counts["opposes"]),
        "n_informs": str(counts["informs"]), "n_consistent": str(counts["consistent-with"]),
        "exp_rows": exp_rows, "res_rows": res_rows, "iss_items": iss_items or "<li>None recorded.</li>",
        "rel_section": (f'<h3>Relations between attempts</h3><ul class="dg-rels">{rel_items}</ul>' if rel_items else ""),
        "path_record": _link(que["record"], graph["slug"] + ".json") if que.get("record") else "withheld",
        "url": _esc(url or f"/graphs/{graph['studyId']}"), "notice": notice, "head_extra": head_extra,
        "profile": _esc(graph.get("profile") or ""),
    }
    page = tpl
    for k, v in fill.items():
        page = page.replace("{{" + k + "}}", v)
    leftover = re.findall(r"{{[a-z_]+}}", page)
    assert not leftover, leftover
    return page


def render_index(graphs: list[dict], note: str = "") -> str:
    tpl = _load_template("graph-index.html")
    items = []
    for g in sorted(graphs, key=lambda g: g["studyId"]):
        n_exp = sum(1 for n in g["nodes"] if n["kind"] == "EXP")
        n_res = sum(1 for n in g["nodes"] if n["kind"] == "RES")
        sp = g["sourcePublication"]
        items.append(f'<li><a href="/graphs/{_esc(g["studyId"])}">{_esc(g["title"])}</a><br>'
                     f'<small>{_esc(sp.get("label") or "")} · {n_exp} attempts, {n_res} findings · headline <code>{_esc(g["outcomeClass"])}</code></small></li>')
    page = tpl.replace("{{items}}", "\n".join(items)).replace("{{note}}", note).replace("{{count}}", str(len(graphs)))
    assert "{{" not in page
    return page
