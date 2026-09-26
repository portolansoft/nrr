"""Load the NRR v0.2 JSON Schema and vocabularies; validate records.

`validate` combines JSON Schema validation with the cross-field rules in `nrr.rules`
(informativeness versus outcome class), so a record that passes here is a record
the registry would accept.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from nrr.rules import enforce_outcome

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
PROFILE_URI = "https://portolansoft.com/profile/nrr/0.2"


# Where the schema inlines a controlled list. vocabularies.json is the source of truth; the schema file
# carries literal enums so it can be published standalone, and these bindings keep the two in step.
ENUM_BINDINGS: dict[str, str] = {
    "properties/kind": "kind",
    "properties/attemptType": "attemptType",
    "properties/pathType": "pathType",
    "properties/visibility": "visibility",
    "properties/domainTags/items": "domainTag",
    "properties/outcomeClass": "outcomeClass",
    "properties/abandonmentReasons/items": "abandonmentReason",
    "$defs/EntityRef/properties/type": "entityType",
    "$defs/Entity/properties/type": "entityType",
    "$defs/Control/properties/kind": "+controlKind",
    "$defs/Finding/properties/outcomeClass": "outcomeClass",
    "$defs/Finding/properties/informativeness": "informativeness",
    "$defs/Finding/properties/failureModes/items": "failureMode",
    "$defs/ScreenedItem/properties/type": "screenedType",
    "$defs/ScreenedItem/properties/decision": "screenedDecision",
    "$defs/ScreenedItem/properties/reason": "screenedReason",
    "$defs/Performer/properties/type": "performerType",
    "$defs/Performer/properties/role": "performerRole",
    "$defs/Stage/properties/stage": "stageName",
    "$defs/UntriedBranch/properties/status": "untriedBranchStatus",
    "$defs/StatusAtCheck/properties/version": "statusVersion",
    "$defs/StatusAtCheck/properties/integrity": "statusIntegrity",
    "$defs/Source/properties/role": "sourceRole",
    "$defs/Relation/properties/type": "relationType",
}


def vocab_for_binding(pointer: str) -> list[str]:
    name = ENUM_BINDINGS[pointer]
    if name == "+controlKind":          # Control.kind is the union of the two control vocabularies
        v = _vocabularies()
        return sorted(set(v["positiveControlKind"]) | set(v["negativeControlKind"]))
    return list(_vocabularies()[name])


def sync_enums(schema: dict) -> dict:
    """Rewrite every inlined enum from vocabularies.json, so the two can never disagree at runtime."""
    for pointer in ENUM_BINDINGS:
        node = schema
        for part in pointer.split("/"):
            node = node[part]
        node["enum"] = vocab_for_binding(pointer)
    return schema


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return sync_enums(json.loads((SCHEMA_DIR / "nrr-0.2.schema.json").read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _vocabularies() -> dict:
    return json.loads((SCHEMA_DIR / "vocabularies.json").read_text(encoding="utf-8"))


def load_vocab(name: str) -> list[str]:
    return list(_vocabularies()[name])


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema(), format_checker=FormatChecker())


def validate(record: dict) -> list[str]:
    """Return a list of human-readable problems; an empty list means the record is valid."""
    problems: list[str] = []
    for err in sorted(_validator().iter_errors(record), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path) or "<root>"
        problems.append(f"{path}: {err.message}")
    for i, finding in enumerate(record.get("findings") or []):
        for msg in enforce_outcome(finding):
            problems.append(f"findings/{i}: {msg}")
    return problems
