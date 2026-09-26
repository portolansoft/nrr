"""Content addressing for records: sha256 over canonical JSON, ignoring identity fields."""
from __future__ import annotations

import hashlib
import json

# `hasPart` is registry-derived (the set of records whose isPartOf points here), so it is excluded
# from the address; otherwise a path and its attempts would each need the other's hash first.
IDENTITY_FIELDS = {"@id", "contentAddress", "dateCreated", "integrity", "hasPart"}


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_address(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in IDENTITY_FIELDS}
    digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return f"urn:portolan:nrr:sha256:{digest}"
