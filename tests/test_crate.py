import json

from nrr.crate import to_crate
from nrr.schema import PROFILE_URI
from tests.factories import minimal_attempt, minimal_path


def _graph(crate):
    return {e["@id"]: e for e in crate["@graph"]}


def test_crate_has_descriptor_and_root():
    g = _graph(to_crate(minimal_attempt()))
    desc = g["ro-crate-metadata.json"]
    assert desc["about"] == {"@id": "./"}
    assert {"@id": "https://w3id.org/ro/crate/1.2"} in desc["conformsTo"]
    assert {"@id": PROFILE_URI} in desc["conformsTo"]
    assert g["./"]["@type"] == "Dataset"


def test_root_carries_record_identity_and_profile():
    rec = minimal_attempt()
    g = _graph(to_crate(rec))
    root = g["./"]
    assert root["identifier"] == rec["@id"]
    assert root["conformsTo"] == {"@id": PROFILE_URI}
    assert root["license"] == {"@id": rec["license"]}


def test_attempt_becomes_prov_activity_with_action_status():
    g = _graph(to_crate(minimal_attempt(outcomeClass="negative-no-effect")))
    act = g["#attempt"]
    assert "prov:Activity" in act["@type"]
    assert act["actionStatus"] == "FailedActionStatus"
    g2 = _graph(to_crate(minimal_attempt(outcomeClass="positive")))
    assert g2["#attempt"]["actionStatus"] == "CompletedActionStatus"


def test_findings_become_entities_and_results():
    rec = minimal_attempt()
    rec["findings"].append(dict(rec["findings"][0], id="f2"))
    g = _graph(to_crate(rec))
    assert "#finding-f1" in g and "#finding-f2" in g
    assert {"@id": "#finding-f1"} in g["#attempt"]["result"]
    assert g["#finding-f1"]["nrr:outcomeClass"] == "negative-no-effect"


def test_is_part_of_becomes_root_relation():
    parent = "urn:portolan:nrr:sha256:" + "1" * 64
    g = _graph(to_crate(minimal_attempt(isPartOf=parent)))
    assert g["./"]["isPartOf"] == {"@id": parent}


def test_path_lists_parts():
    rec = minimal_path()
    g = _graph(to_crate(rec))
    assert g["./"]["hasPart"] == [{"@id": rec["hasPart"][0]}]


def test_sources_and_operator_are_graph_nodes():
    g = _graph(to_crate(minimal_attempt()))
    assert g["#operator"]["name"] == "Example Lab"
    assert "https://doi.org/10.1038/s41586-026-10652-y" in g
    assert g["https://doi.org/10.1038/s41586-026-10652-y"]["@type"] == "ScholarlyArticle"


def test_graph_ids_are_unique_and_json_serialisable():
    crate = to_crate(minimal_attempt())
    ids = [e["@id"] for e in crate["@graph"]]
    assert len(ids) == len(set(ids))
    json.dumps(crate)
