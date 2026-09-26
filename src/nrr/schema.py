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


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return json.loads((SCHEMA_DIR / "nrr-0.2.schema.json").read_text(encoding="utf-8"))


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
