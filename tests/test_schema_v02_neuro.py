"""Schema additions forced by the Arcadia neuroimaging study (in vivo animal work, imaging, adaptive protocols)."""
import pytest

from nrr.rules import apply_informativeness, informativeness
from nrr.schema import load_vocab, validate
from tests.factories import minimal_attempt


# ---- vocabulary additions ----------------------------------------------------------------

def test_within_subject_negative_control_kind_exists():
    assert "within-subject" in load_vocab("negativeControlKind")


def test_new_failure_modes_exist():
    fm = load_vocab("failureMode")
    assert "irreproducible-across-trials" in fm
    assert "signal-below-noise" in fm


def test_credit_performer_roles_exist():
    roles = load_vocab("performerRole")
    for r in ("validation", "methodology", "software"):
        assert r in roles, r


def test_anatomical_structure_entity_type_exists():
    assert "anatomicalStructure" in load_vocab("entityType")


# ---- field additions ---------------------------------------------------------------------

def test_within_subject_control_validates_on_a_finding():
    rec = minimal_attempt()
    rec["findings"][0]["controls"]["negative"] = {
        "kind": "within-subject", "label": "ipsilateral hemisphere", "observed": "no localized response", "passed": True}
    assert validate(rec) == []


def test_finding_accepts_arrive_reporting_fields():
    rec = minimal_attempt()
    rec["findings"][0].update({
        "blinding": "not stated",
        "randomization": "not applicable; one animal per trial",
        "preregistration": "none",
        "reportingGuideline": "ARRIVE 2.0 not cited",
    })
    assert validate(rec) == []


def test_stage_accepts_protocol_adaptations():
    rec = minimal_attempt()
    rec["stages"] = [{
        "stage": "experiment",
        "performedBy": [{"name": "lab", "type": "person", "role": "experiment-execution"}],
        "protocolAdaptations": ["reduced the isoflurane level by 0.25%", "placed the stimulator on a different limb"],
    }]
    assert validate(rec) == []


def test_data_pointer_accepts_run_id():
    rec = minimal_attempt()
    rec["findings"][0]["evidence"][0]["data"] = [{
        "label": "imaging run", "repository": "Zenodo", "accession": "10.5281/zenodo.11585535",
        "runId": "2024-02-29/Zyla_5min_RHLstim_2son4soff_1pt25pctISO_1", "checksum": "md5:f5d7d2b33f4e5fec75a4991ab3e9b94e"}]
    assert validate(rec) == []


# ---- the rule clause this study fires for the first time -----------------------------------

def _itch_finding():
    return {
        "outcomeClass": "negative-no-effect",
        "controls": {
            # the tactile response in the same session, and capsaicin in the same animals, are internal positives
            "positive": {"kind": "internal-positive", "label": "tactile response in the same session", "passed": True},
            # saline produced the same widespread activation as histamine: the control is not clean
            "negative": {"kind": "vehicle", "label": "PBS", "observed": "widespread bilateral activation of similar magnitude", "passed": False},
        },
    }


def test_dirty_negative_control_makes_a_finding_uninformative_even_with_a_passing_positive():
    label, reason = informativeness(_itch_finding())
    assert label == "uninformative"
    assert "negative control not clean" in reason
    assert "positive control" not in reason        # the positive control is not the problem here


def test_dirty_negative_control_maps_to_controls_failed_not_no_positive_control():
    f = _itch_finding()
    apply_informativeness(f)
    assert f["outcomeClass"] == "inconclusive-controls-failed"
    assert f["informativeness"] == "uninformative"
