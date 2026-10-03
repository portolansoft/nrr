"""The capture profile: what a record emitted at run time must carry.

The full NRR v0.2 schema is a superset of about a hundred fields and nobody fills it by hand. The capture profile is
the subset an agent or a lab system must write while it still has the information, because the post-hoc ingest of
nine published studies showed that exactly these things are gone by publication: who proposed a candidate and under
which model, how many runs there were, which raw files a claim rests on, and whether the run could have seen the
effect it did not see.

A capture record is a valid v0.2 `attempt` (so `nrr.schema.validate` passes) that additionally satisfies:

1. at least one finding, and every finding has a question, a target, an outcome class and controls (schema already);
2. every finding has at least one evidence item that points at raw bytes: a `data[]` pointer with a `checksum` or a
   `runId`, so the claim can be re-derived from what the instrument or agent actually produced;
3. a negative or inconclusive finding carries a `sensitivity` or `power` statement, or the record says in the
   finding's `note` that none exists (the rule will mark it uninformative either way, but silence is not allowed);
4. at least one stage with a `startTime` or `endTime`, so the record is anchored in time rather than in a build date;
5. at least one performer, and every `software-agent` or `llm` performer names a `model`, a `commit` or a `version`;
6. `dateCreated` is the run's own time, not the ingest default.

Errors are things a capture must fix; warnings are things it should. `check_capture` returns both.
"""
from __future__ import annotations

from nrr.ingest.common import INGEST_DATE
from nrr.schema import validate

NEGATIVE_PREFIXES = ("negative-", "inconclusive")


def check_capture(record: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a capture-time record."""
    errors = [f"schema: {p}" for p in validate(record)]
    warnings: list[str] = []
    if record.get("kind") != "attempt":
        errors.append("capture records are attempts; paths are assembled by the registry from isPartOf")
    findings = record.get("findings") or []
    if not findings:
        errors.append("no findings")
    for f in findings:
        fid = f.get("id", "?")
        pointers = [d for e in f.get("evidence", []) for d in e.get("data", [])]
        if not any(d.get("checksum") or d.get("runId") for d in pointers):
            errors.append(f"finding {fid}: no evidence pointer with a checksum or runId")
        if f.get("outcomeClass", "").startswith(NEGATIVE_PREFIXES) and not (f.get("sensitivity") or f.get("power")):
            if "sensitivity" in (f.get("note") or "").lower() or "detection" in (f.get("note") or "").lower():
                warnings.append(f"finding {fid}: negative without a sensitivity or power statement; the note says why, and the rule will mark it uninformative")
            else:
                errors.append(f"finding {fid}: negative without a sensitivity or power statement and no note saying why")
        if (f.get("target") or {}).get("identifier") is None and "identifier" not in (f.get("target") or {}).get("note", ""):
            warnings.append(f"finding {fid}: target has no identifier")
    stages = record.get("stages") or []
    if not stages:
        errors.append("no stages")
    elif not any(s.get("startTime") or s.get("endTime") for s in stages):
        errors.append("no stage carries a startTime or endTime")
    performers = record.get("performers") or []
    if not performers:
        errors.append("no performers")
    for p in performers:
        if p.get("type") in ("software-agent", "llm") and not (p.get("model") or p.get("commit") or p.get("version")):
            errors.append(f"performer {p.get('name')}: software performer without model, commit or version")
    if record.get("dateCreated") == INGEST_DATE:
        warnings.append("dateCreated is the ingest default, not the run's own time")
    return errors, warnings
