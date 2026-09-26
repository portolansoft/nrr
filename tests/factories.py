"""Test factories: minimal records that should validate against NRR v0.2."""
from __future__ import annotations

import copy

MINIMAL_ATTEMPT = {
    "@id": "urn:portolan:nrr:sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "kind": "attempt",
    "studyId": "example-study",
    "slug": "example-attempt",
    "title": "Example attempt",
    "profile": "https://portolansoft.com/profile/nrr/0.2",
    "version": "1",
    "dateCreated": "2026-09-25T00:00:00Z",
    "license": "https://creativecommons.org/publicdomain/zero/1.0/",
    "visibility": "public",
    "operator": {"name": "Example Lab", "identifier": "https://ror.org/000000000"},
    "domainTags": ["biology"],
    "attemptType": "wet-lab",
    "question": "Does drug X increase phagocytosis in ARPE-19 cells?",
    "successCriteria": "Normalised MFI above vehicle by Dunnett's test, P < 0.05.",
    "pathType": "experiment",
    "outcomeClass": "negative-no-effect",
    "findings": [
        {
            "id": "f1",
            "question": "Does drug X increase phagocytosis in ARPE-19 cells?",
            "target": {"label": "drug X", "identifier": "pubchem:CID1"},
            "outcomeClass": "negative-no-effect",
            "informativeness": "informative",
            "controls": {
                "positive": {"kind": "designated", "label": "MFGE8", "expected": "increase", "observed": "1.46x", "passed": True},
                "negative": {"kind": "vehicle", "label": "DMSO 0.5%", "observed": "1.0x", "passed": True},
            },
            "sensitivity": "assay resolves 1.4x change at n=3 wells",
            "evidence": [{"label": "Supp Table 3", "source": "10.1038/s41586-026-10652-y#MOESM3", "values": {"mean": 1.01}}],
        }
    ],
    "applicabilityConditions": {"organism": "NCBITaxon:9606", "cellLine": "CVCL_0145"},
    "cost": {"wetLabRuns": 1},
    "sources": [{"role": "source-publication", "identifier": "doi:10.1038/s41586-026-10652-y"}],
}


def minimal_attempt(**overrides) -> dict:
    rec = copy.deepcopy(MINIMAL_ATTEMPT)
    rec.update(overrides)
    return rec


def minimal_path(**overrides) -> dict:
    rec = copy.deepcopy(MINIMAL_ATTEMPT)
    rec["kind"] = "path"
    rec.pop("attemptType")
    rec.pop("findings")
    rec["hasPart"] = ["urn:portolan:nrr:sha256:" + "1" * 64]
    rec.update(overrides)
    return rec
