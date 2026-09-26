import pytest

from nrr.schema import load_schema, load_vocab, validate
from tests.factories import minimal_attempt, minimal_path


def test_schema_loads_and_declares_draft_2020_12():
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "Finding" in schema["$defs"]


def test_minimal_attempt_validates():
    assert validate(minimal_attempt()) == []


def test_minimal_path_validates():
    assert validate(minimal_path()) == []


def test_missing_question_is_reported():
    rec = minimal_attempt()
    del rec["question"]
    errors = validate(rec)
    assert any("question" in e for e in errors)


def test_unknown_outcome_class_is_rejected():
    rec = minimal_attempt(outcomeClass="negative-because-i-said-so")
    errors = validate(rec)
    assert errors and any("outcomeClass" in e for e in errors)


def test_unknown_attempt_type_is_rejected():
    rec = minimal_attempt(attemptType="vibes")
    assert validate(rec)


def test_path_requires_has_part():
    rec = minimal_path()
    del rec["hasPart"]
    assert validate(rec)


def test_attempt_requires_at_least_one_finding():
    rec = minimal_attempt(findings=[])
    assert validate(rec)


def test_finding_outcome_must_be_in_vocab():
    rec = minimal_attempt()
    rec["findings"][0]["outcomeClass"] = "nope"
    assert validate(rec)


def test_positive_control_kind_is_constrained():
    rec = minimal_attempt()
    rec["findings"][0]["controls"]["positive"]["kind"] = "imaginary"
    assert validate(rec)


def test_vocab_lists_available():
    assert "negative-no-effect" in load_vocab("outcomeClass")
    assert "inconclusive-no-positive-control" in load_vocab("outcomeClass")
    assert "transformation-failed" in load_vocab("failureMode")
    assert "phenotype-nonspecific" in load_vocab("failureMode")
    assert "not-selected-for-testing" in load_vocab("screenedReason")
    assert "technical-gap" in load_vocab("abandonmentReason")
    assert "hypothesis-generation" in load_vocab("performerRole")
