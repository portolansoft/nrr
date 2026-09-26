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


def test_inlined_enums_match_the_vocabulary_file():
    """The schema file carries literal enums so it can be published standalone; they must not drift
    from vocabularies.json, which is the single source of truth."""
    from nrr.schema import ENUM_BINDINGS, _vocabularies, vocab_for_binding
    import json as _json
    from pathlib import Path as _Path
    from nrr.schema import SCHEMA_DIR
    on_disk = _json.loads((SCHEMA_DIR / "nrr-0.2.schema.json").read_text(encoding="utf-8"))
    problems = []
    for pointer in ENUM_BINDINGS:
        node = on_disk
        for part in pointer.split("/"):
            node = node[part]
        if node.get("enum") != vocab_for_binding(pointer):
            problems.append(pointer)
    assert problems == [], problems


def test_entity_accepts_a_note():
    from tests.factories import minimal_attempt
    rec = minimal_attempt()
    rec["entities"] = [{"id": "UBERON:0008933", "type": "anatomicalStructure", "label": "S1",
                        "note": "nearest exact ontology match"}]
    assert validate(rec) == []
