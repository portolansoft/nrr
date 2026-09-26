"""Shared constructors for converters: identity, sources, entities, performers, statistics."""
from __future__ import annotations

import csv
import json
import os
import statistics
from pathlib import Path

import yaml

from nrr.identity import content_address
from nrr.schema import PROFILE_URI, validate

INGEST_DATE = os.environ.get("NRR_BUILD_DATE", "2026-09-25T00:00:00Z")
RECORD_LICENSE = "https://creativecommons.org/publicdomain/zero/1.0/"


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean_sem(values: list[float]) -> tuple[float, float | None]:
    m = statistics.fmean(values)
    sem = statistics.stdev(values) / len(values) ** 0.5 if len(values) > 1 else None
    return m, sem


def new_record(kind: str, study_id: str, slug: str, title: str, operator: dict, **fields) -> dict:
    rec = {
        "@id": "urn:portolan:nrr:sha256:" + "0" * 64,
        "kind": kind,
        "profile": PROFILE_URI,
        "version": "1",
        "dateCreated": INGEST_DATE,
        "license": RECORD_LICENSE,
        "visibility": "public",
        "studyId": study_id,
        "slug": slug,
        "title": title,
        "operator": operator,
        "domainTags": ["biology"],
    }
    rec.update(fields)
    return rec


def strip_none(obj):
    """Drop None-valued keys recursively; optional fields are absent, never null."""
    if isinstance(obj, dict):
        return {k: strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [strip_none(v) for v in obj]
    return obj


def finalize(rec: dict, check: bool = True) -> dict:
    """Compute the content address, stamp integrity, and (by default) validate; raise on invalid.

    Paths are finalized before their attempts exist (hasPart is registry-derived and outside the
    address), so callers fill hasPart afterwards and call `check_valid`."""
    cleaned = strip_none({k: v for k, v in rec.items() if k != "integrity"})
    rec.clear()
    rec.update(cleaned)
    addr = content_address(rec)
    rec["@id"] = addr
    rec["contentAddress"] = addr
    rec["integrity"] = {"contentAddress": addr, "signature": None, "signer": None, "trustTier": "pilot-unsigned", "duplicateOf": None}
    if check:
        check_valid(rec)
    return rec


def check_valid(rec: dict) -> dict:
    problems = validate(rec)
    if problems:
        raise ValueError(f"record {rec.get('slug')} invalid: {problems[:5]}")
    return rec


def status_at_check(resolver, doi: str) -> dict:
    st = resolver.doi_status(doi)
    asserted = st.get("assertedBy", "not-checked")
    # An offline miss carries no real check time; use the build date so content addresses stay reproducible.
    checked = st.get("checkedAt", INGEST_DATE) if asserted != "not-checked" else INGEST_DATE
    return {"version": st.get("version", "unknown"), "integrity": st.get("integrity", "unknown"),
            "assertedBy": asserted, "checkedAt": checked}


def source(role: str, identifier: str, resolver=None, **extra) -> dict:
    src = {"role": role, "identifier": identifier}
    if resolver is not None and identifier.startswith("doi:"):
        src["statusAtCheck"] = status_at_check(resolver, identifier[4:])
    src.update({k: v for k, v in extra.items() if v is not None})
    return src


def entity(id_: str, type_: str, label: str, **extra) -> dict:
    e = {"id": id_, "type": type_, "label": label}
    e.update({k: v for k, v in extra.items() if v is not None})
    return e


def performer(name: str, type_: str, role: str, **extra) -> dict:
    p = {"name": name, "type": type_, "role": role}
    p.update({k: v for k, v in extra.items() if v is not None})
    return p


def data_pointer(label: str, **extra) -> dict:
    d = {"label": label}
    d.update({k: v for k, v in extra.items() if v is not None})
    return d


def compound_ref(resolver, label: str, fallback_type: str = "compound") -> dict:
    """EntityRef for a compound name, using the resolver cache; unresolved names stay label-only."""
    hit = resolver.compound(label)
    if hit and hit.get("identifier"):
        return {"label": label, "identifier": hit["identifier"], "type": "compound"}
    return {"label": label, "type": fallback_type, "note": "identifier not resolved"}
