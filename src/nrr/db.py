"""SQLite loader and named queries over the NRR corpus (the reuse surface a future MCP would wrap)."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from nrr.crate import to_crate

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def _queries() -> dict[str, str]:
    out: dict[str, str] = {}
    text = (DB_DIR / "queries.sql").read_text(encoding="utf-8")
    for block in re.split(r"\n(?=-- name: )", text):
        m = re.match(r"-- name: (\S+)\n(.*)", block.strip(), re.S)
        if m:
            sql = "\n".join(l for l in m.group(2).splitlines() if not l.startswith("--"))
            out[m.group(1)] = sql.strip()
    return out


def load(records: list[dict], db_path: Path | str) -> None:
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
    for rec in records:
        crate = to_crate(rec)
        con.execute(
            "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["@id"], rec["slug"], rec["studyId"], rec["kind"], rec.get("attemptType"), rec["title"], rec["question"],
             rec["outcomeClass"], rec.get("outcomeSummary"), rec["operator"]["name"], rec.get("isPartOf"), rec["dateCreated"],
             rec["visibility"], rec.get("sourceLicense"), json.dumps(rec.get("applicabilityConditions"), ensure_ascii=False),
             json.dumps(rec.get("cost"), ensure_ascii=False), json.dumps(rec, ensure_ascii=False, sort_keys=True), json.dumps(crate, ensure_ascii=False)),
        )
        findings_text = []
        for f in rec.get("findings", []):
            c = f.get("controls", {})
            pos, neg = c.get("positive", {}), c.get("negative", {})
            eff = f.get("effect", {})
            con.execute(
                "INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rec["@id"], f["id"], f["question"], f["target"]["label"], f["target"].get("identifier"), f["target"].get("type"),
                 f["outcomeClass"], f["informativeness"], f.get("informativenessReason"), json.dumps(f.get("failureModes", [])),
                 eff.get("metric"), None if eff.get("value") is None else str(eff.get("value")), eff.get("n"), eff.get("direction"),
                 None if eff.get("significant") is None else str(eff.get("significant")),
                 pos.get("kind"), None if pos.get("passed") is None else int(pos["passed"]), neg.get("kind"),
                 None if neg.get("passed") is None else int(neg["passed"]), f.get("sensitivity"), (f.get("conditions") or {}).get("dose"),
                 f.get("proposedBy"), json.dumps(f, ensure_ascii=False)),
            )
            findings_text.append(f"{f['question']} {f['target']['label']} {f['outcomeClass']} {json.dumps(f.get('conditions', {}), ensure_ascii=False)}")
        for i, s in enumerate(rec.get("screened", [])):
            sc = s.get("score") or {}
            con.execute("INSERT INTO screened_items VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (rec["@id"], i, s["label"], s.get("identifier"), s["type"], s.get("proposedBy"), s["decision"], s["reason"],
                         sc.get("method"), sc.get("value"), sc.get("rank")))
        for e in rec.get("entities", []):
            con.execute("INSERT OR IGNORE INTO entities VALUES (?,?,?,?,?)", (e["id"], e["type"], e["label"], e.get("scheme"), e.get("url")))
            con.execute("INSERT OR IGNORE INTO record_entities VALUES (?,?,?)", (rec["@id"], e["id"], e.get("role")))
        for i, p in enumerate(rec.get("performers", [])):
            con.execute("INSERT INTO performers VALUES (?,?,?,?,?,?,?,?,?)",
                        (rec["@id"], i, p["name"], p["type"], p["role"], p.get("model"), p.get("provider"), p.get("version"), p.get("commit")))
        for rel in rec.get("relations", []):
            con.execute("INSERT OR IGNORE INTO relations VALUES (?,?,?,?)", (rec["@id"], rel["type"], rel["target"], rel.get("note")))
        for i, s in enumerate(rec.get("sources", [])):
            st = s.get("statusAtCheck") or {}
            con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (rec["@id"], i, s["role"], s["identifier"], s.get("label"), st.get("version"), st.get("integrity"), st.get("assertedBy"), st.get("checkedAt"), len(s.get("data", []))))
        for i, b in enumerate(rec.get("untriedBranches", [])):
            con.execute("INSERT INTO branches VALUES (?,?,?,?,?,?)", (rec["@id"], i, "untried-branch", b["status"], b["description"], len(b.get("dataAvailable", []))))
        for i, q in enumerate(rec.get("openQuestions", [])):
            con.execute("INSERT INTO branches VALUES (?,?,?,?,?,?)", (rec["@id"], i, "open-question", "asked-by-authors", q, 0))
        branch_texts = {b["description"] for b in rec.get("untriedBranches", [])}
        for i, q in enumerate(rec.get("nextSteps", [])):
            if q not in branch_texts:  # nextSteps that are already structured untried branches are not repeated
                con.execute("INSERT INTO branches VALUES (?,?,?,?,?,?)", (rec["@id"], i, "next-step", "proposed-by-authors", q, 0))
        rowid = con.execute("SELECT rowid FROM records WHERE id = ?", (rec["@id"],)).fetchone()[0]
        entity_text = " ".join(e["label"] for e in rec.get("entities", []))
        con.execute("INSERT INTO records_fts(rowid, slug, title, question, outcome_summary, applicability, findings_text) VALUES (?,?,?,?,?,?,?)",
                    (rowid, rec["slug"], rec["title"], rec["question"], rec.get("outcomeSummary", ""),
                     json.dumps(rec.get("applicabilityConditions"), ensure_ascii=False) + " " + entity_text, " ".join(findings_text)))
    con.commit()
    con.close()


def query(db_path: Path | str, query_name: str, **params) -> list[dict]:
    sql = _queries()[query_name]
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows


def query_names() -> list[str]:
    return list(_queries())
