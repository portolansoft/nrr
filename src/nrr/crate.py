"""Serialise a canonical NRR record as an RO-Crate 1.2 detached crate (JSON-LD).

The canonical JSON record is the source of truth; the crate is derived from it so that
DOE data services, WorkflowHub and Dataverse-style consumers get schema.org + PROV terms.
Portolan-specific properties are namespaced `nrr:`.
"""
from __future__ import annotations

import re

from nrr.schema import PROFILE_URI

NRR_NS = "https://portolansoft.com/schema/nrr/0.2#"
CONTEXT = ["https://w3id.org/ro/crate/1.2/context", {"prov": "http://www.w3.org/ns/prov#", "nrr": NRR_NS}]

ACTION_TYPE = {
    "wet-lab": "CreateAction",
    "computational": "AssessAction",
    "evidence-synthesis": "SearchAction",
    "hypothesis-generation": "SearchAction",
    "evaluation": "AssessAction",
}
SOURCE_TYPE = {
    "source-publication": "ScholarlyArticle",
    "prior-art": "ScholarlyArticle",
    "reference": "ScholarlyArticle",
    "comparator": "ScholarlyArticle",
    "data-deposit": "Dataset",
    "supplementary": "Dataset",
    "code-repository": "SoftwareSourceCode",
    "trajectory": "Dataset",
    "sample-trajectory": "Dataset",
    "protocol": "HowTo",
}
ENTITY_TYPE = {
    "organism": "Taxon", "strain": "Taxon", "cellLine": "BioChemEntity", "cellType": "DefinedTerm",
    "gene": "Gene", "protein": "Protein", "compound": "ChemicalSubstance", "reagent": "Product",
    "assay": "DefinedTerm", "disease": "MedicalCondition", "process": "DefinedTerm", "instrument": "Product",
    "software": "SoftwareApplication", "agent": "SoftwareApplication", "organization": "Organization",
    "dataset": "Dataset", "plate": "Thing", "locus": "Gene", "protocol": "HowTo", "medium": "Product", "other": "Thing",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _source_id(identifier: str) -> str:
    if identifier.startswith("doi:"):
        return "https://doi.org/" + identifier[4:]
    return identifier


def _prefixed(obj: dict, skip: set[str] = frozenset()) -> dict:
    return {f"nrr:{k}": v for k, v in obj.items() if k not in skip}


def to_crate(record: dict) -> dict:
    graph: list[dict] = []
    seen: set[str] = set()

    def add(node: dict) -> None:
        if node["@id"] in seen:
            return
        seen.add(node["@id"])
        graph.append(node)

    add({
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "conformsTo": [{"@id": "https://w3id.org/ro/crate/1.2"}, {"@id": PROFILE_URI}],
        "about": {"@id": "./"},
    })

    root: dict = {
        "@id": "./",
        "@type": "Dataset",
        "identifier": record["@id"],
        "name": record["title"],
        "description": record["question"],
        "datePublished": record["dateCreated"],
        "license": {"@id": record["license"]},
        "conformsTo": {"@id": PROFILE_URI},
        "version": record["version"],
        "nrr:kind": record["kind"],
        "nrr:studyId": record["studyId"],
        "nrr:slug": record["slug"],
        "nrr:outcomeClass": record["outcomeClass"],
        "nrr:visibility": record["visibility"],
        "nrr:pathType": record["pathType"],
        "nrr:successCriteria": record["successCriteria"],
        "keywords": record.get("domainTags", []),
        "hasPart": [],
        "prov:wasAttributedTo": [{"@id": "#operator"}],
    }
    for key in ("applicabilityConditions", "invalidators", "untriedBranches", "openQuestions", "abandonmentReasons",
                "cost", "provenanceNotes", "sourceLicense", "aiUseDeclaration", "confidence", "outcomeSummary",
                "hypothesis", "nextSteps", "screenedSummary", "governance", "embargoUntil"):
        if key in record:
            root[f"nrr:{key}"] = record[key]
    if record.get("isPartOf"):
        root["isPartOf"] = {"@id": record["isPartOf"]}
    if record.get("hasPart"):
        root["hasPart"] = [{"@id": p} for p in record["hasPart"]]
    if record.get("isNewVersionOf"):
        root["nrr:isNewVersionOf"] = {"@id": record["isNewVersionOf"]}

    op = record["operator"]
    add({"@id": "#operator", "@type": op.get("type", "Organization"), "name": op["name"],
         **({"identifier": op["identifier"]} if op.get("identifier") else {})})

    performer_ids: list[dict] = []
    for perf in record.get("performers", []):
        pid = f"#performer-{_slug(perf['name'] + '-' + perf['role'])}"
        ptype = ["SoftwareApplication", "prov:SoftwareAgent"] if perf["type"] in ("software-agent", "llm") else \
                ["Person", "prov:Person"] if perf["type"] == "person" else ["Organization", "prov:Agent"]
        add({"@id": pid, "@type": ptype, "name": perf["name"], **_prefixed(perf, skip={"name"})})
        performer_ids.append({"@id": pid})
    if performer_ids:
        root["prov:wasAttributedTo"].extend(performer_ids)

    if record["kind"] == "attempt":
        status = "CompletedActionStatus" if record["outcomeClass"] in ("positive", "partial") else "FailedActionStatus"
        act: dict = {
            "@id": "#attempt",
            "@type": [ACTION_TYPE.get(record.get("attemptType", "wet-lab"), "Action"), "prov:Activity"],
            "name": record["title"],
            "description": record["question"],
            "actionStatus": status,
            "nrr:attemptType": record.get("attemptType"),
            "nrr:outcomeClass": record["outcomeClass"],
            "agent": {"@id": "#operator"},
            "instrument": performer_ids,
            "object": [{"@id": t["identifier"]} if t.get("identifier") else {"name": t["label"]} for t in record.get("target", [])],
            "result": [],
        }
        root["mainEntity"] = {"@id": "#attempt"}
        root["hasPart"].append({"@id": "#attempt"})
        for f in record.get("findings", []):
            fid = f"#finding-{_slug(f['id'])}"
            add({"@id": fid, "@type": ["nrr:Finding", "prov:Entity"], "name": f["question"],
                 "prov:wasGeneratedBy": {"@id": "#attempt"}, **_prefixed(f, skip={"id"})})
            act["result"].append({"@id": fid})
            root["hasPart"].append({"@id": fid})
        for i, s in enumerate(record.get("screened", []), start=1):
            sid = f"#screened-{i}"
            add({"@id": sid, "@type": "nrr:ScreenedItem", "name": s["label"], **_prefixed(s, skip={"label"})})
            root["hasPart"].append({"@id": sid})
        for i, st in enumerate(record.get("stages", []), start=1):
            sid = f"#stage-{i}-{_slug(st['stage'])}"
            add({"@id": sid, "@type": ["Action", "prov:Activity"], "name": st.get("label", st["stage"]),
                 "nrr:stage": st["stage"], **_prefixed(st, skip={"stage", "label"})})
            act.setdefault("hasPart", []).append({"@id": sid})
        add(act)

    for src in record.get("sources", []):
        sid = _source_id(src["identifier"])
        node = {"@id": sid, "@type": SOURCE_TYPE.get(src["role"], "CreativeWork"), "nrr:role": src["role"]}
        for k in ("label", "url", "checksum", "statusAtCheck", "license", "note", "data"):
            if k in src:
                node["name" if k == "label" else f"nrr:{k}"] = src[k]
        add(node)
        if src["role"] in ("source-publication",):
            root.setdefault("isSupplementTo", []).append({"@id": sid})
        else:
            root.setdefault("prov:used", []).append({"@id": sid})

    for ent in record.get("entities", []):
        node = {"@id": ent["id"], "@type": ENTITY_TYPE.get(ent["type"], "Thing"), "name": ent["label"], "nrr:entityType": ent["type"]}
        for k in ("role", "scheme", "url", "altIds", "extra"):
            if k in ent:
                node[f"nrr:{k}"] = ent[k]
        add(node)
        root.setdefault("mentions", []).append({"@id": ent["id"]})

    for rel in record.get("relations", []):
        key = {"wasDerivedFrom": "prov:wasDerivedFrom", "used": "prov:used", "wasGeneratedBy": "prov:wasGeneratedBy"}.get(rel["type"], f"nrr:{rel['type']}")
        root.setdefault(key, []).append({"@id": rel["target"]})

    graph.insert(1, root)
    return {"@context": CONTEXT, "@graph": graph}
