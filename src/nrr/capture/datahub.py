"""Emit a capture-time record from an Arcadia Data Hub instrument run (MIT, github.com/Arcadia-Science/data-hub).

Data Hub is the measurement layer: a run is an instrument, a run id, acquisition time, extracted metadata and files
with S3 keys and sizes. It has no notion of a question, a control or an outcome, so those come from the agent or
person who ran the experiment, as a `claim`. The emitter joins the two into one NRR attempt whose evidence pointers
carry the Data Hub run id and, when the file bytes are at hand, a sha256 the registry can re-check.

What Data Hub's API does not expose, as of commit 5a2acaa5 (2026-10-03): a per-file checksum. The record therefore
satisfies the capture profile through `runId`, and adds `checksum` only for files the emitter has read.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from nrr.ingest.common import data_pointer, finalize, new_record, performer, source
from nrr.rules import apply_informativeness

DATAHUB_REPO = "https://github.com/Arcadia-Science/data-hub"


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def emit_datahub_run(run: dict, claim: dict, files_dir: Path | None = None, hub_url: str = "") -> list[dict]:
    """One attempt record for one Data Hub run plus the claim made about it.

    `run` is the JSON from GET /api/v1/instruments/{instrumentId}/runs/{runId}. `claim` carries: question, target,
    outcomeClass, controls, effect (optional), sensitivity (when negative), conditions, performers, operator,
    successCriteria, title. `files_dir` holds downloaded run files by filename, for checksums.
    """
    inst, run_id = run["instrument_id"], run["run_id"]
    acquired = run.get("acquired_at") or run["created_at"]
    study = claim.get("studyId") or f"datahub-{_slug(inst)}"
    slug = f"{study}-{_slug(run_id)}"
    operator = {"name": claim["operator"]["name"], "type": "Organization", **({"identifier": claim["operator"]["identifier"]} if claim["operator"].get("identifier") else {})}

    pointers = []
    for f in run.get("files", []):
        local = (files_dir / f["filename"]) if files_dir else None
        checksum = "sha256:" + hashlib.sha256(local.read_bytes()).hexdigest() if local and local.exists() else None
        pointers.append(data_pointer(f["filename"], repository="Arcadia Data Hub (self-hosted)", accession=run_id,
                                     runId=f"{inst}/{run_id}", path=f["s3_key"], url=(hub_url + f["download_url"]) if hub_url and f.get("download_url") else None,
                                     checksum=checksum, size=f.get("size_bytes"), format=f.get("content_type"), role=f"{f.get('category', 'file')} file, status {f.get('status')}",
                                     note=None if checksum else "Data Hub's API exposes no per-file checksum; none computed because the bytes were not fetched"))
    deposit = source("data-deposit", f"datahub:{inst}/{run_id}", label=f"Data Hub run {run_id} on {run.get('instrument_display_name', inst)}",
                     url=f"{hub_url}/instruments/{inst}/runs/{run_id}" if hub_url else None, data=pointers,
                     note="self-hosted instance; the run record, extracted metadata and files are served by its REST API and MCP server")

    people = [performer(a["displayName"], "person", "experiment-execution", identifier=f"datahub-user:{a['userId']}",
                        note="claimed the run in Data Hub (attribution)") for a in run.get("attributions", [])]
    agents = [performer(p["name"], p.get("type", "software-agent"), p.get("role", "data-analysis"), model=p.get("model"), version=p.get("version"),
                        commit=p.get("commit"), provider=p.get("provider")) for p in claim.get("performers", [])]

    finding = {"id": claim.get("findingId", "claim"), "question": claim["question"], "target": claim["target"],
               "outcomeClass": claim["outcomeClass"], "informativeness": "not-applicable",
               "controls": claim["controls"], "conditions": {**run.get("metadata", {}), **claim.get("conditions", {}), "instrument": run.get("instrument_display_name", inst), "acquiredAt": acquired},
               "evidence": [{"label": f"Data Hub run {run_id}", "source": f"datahub:{inst}/{run_id}", "locator": "run files", "data": pointers}]}
    for k in ("effect", "sensitivity", "power", "replicates", "note", "failureModes"):
        if claim.get(k) is not None:
            finding[k] = claim[k]
    apply_informativeness(finding)

    rec = new_record("attempt", study, slug, claim.get("title", f"{claim['question']} ({run_id})"),
                     attemptType="wet-lab", pathType="experiment", question=claim["question"],
                     successCriteria=claim.get("successCriteria", "stated in the claim"), outcomeClass=finding["outcomeClass"], findings=[finding],
                     stages=[{"stage": "instrument-capture", "label": f"{run.get('instrument_display_name', inst)} run {run_id}", "startTime": acquired,
                              "endTime": max([f.get("processed_at") or f.get("uploaded_at") or acquired for f in run.get("files", [])] + [acquired]),
                              "performedBy": people or [performer("unattributed Data Hub user", "person", "experiment-execution", note="run has no attribution in Data Hub")],
                              "instrument": [run.get("instrument_display_name", inst)], "parameters": run.get("metadata", {}), "outputs": pointers,
                              "software": [{"name": "Data Hub", "url": DATAHUB_REPO}], "note": f"Data Hub run source: {run.get('source')}; file processing by the Lambda pipeline"}]
                            + ([{"stage": "analysis", "label": claim["analysis"]["label"], "startTime": claim["analysis"].get("startTime", acquired), "performedBy": agents or people,
                                 "method": claim["analysis"].get("method")}] if claim.get("analysis") else []),
                     performers=people + agents, cost={"note": claim.get("costNote", "one instrument run; cost not recorded by Data Hub")},
                     applicabilityConditions=claim.get("applicabilityConditions", {"instrument": run.get("instrument_display_name", inst)}),
                     sources=[deposit, source("code-repository", DATAHUB_REPO, label="Arcadia Data Hub", url=DATAHUB_REPO, license="MIT")],
                     entities=claim.get("entities", []), operator=operator, sourceLicense=claim.get("sourceLicense", "not stated"),
                     domainTags=claim.get("domainTags", ["biology"]), dateCreated=acquired,
                     provenanceNotes=[
                         "Measurement layer from Data Hub's run JSON (instrument, run id, acquisition time, extracted metadata, files with S3 keys and sizes); claim layer from the attached claim. Data Hub records neither questions nor controls, so everything the informativeness rule reads came from the claim.",
                         *claim.get("provenanceNotes", [])])
    return [finalize(rec)]
