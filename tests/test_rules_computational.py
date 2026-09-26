"""Rule behaviour for computational negatives, forced by the Arcadia Raman batch-effects study.

There the controls are not reagents. The positive control is a different prediction task on the same
data and pipeline that is known to carry signal (species instead of strain). The negative control is an
adversarial task: predicting a label that should carry no signal at all (which plate a spectrum came from).
"""
from nrr.rules import apply_informativeness, informativeness
from nrr.schema import load_vocab, validate
from tests.factories import minimal_attempt


def test_computational_control_kinds_exist():
    assert "known-positive-task" in load_vocab("positiveControlKind")
    assert "adversarial-label" in load_vocab("negativeControlKind")


def test_train_test_leakage_failure_mode_exists():
    assert "train-test-leakage" in load_vocab("failureMode")


def test_effect_accepts_a_range_and_a_chance_baseline():
    rec = minimal_attempt()
    rec["findings"][0]["effect"] = {
        "metric": "multiclass Matthews correlation coefficient, median across folds",
        "value": 0.32, "range": [0.19, 0.42], "n": 3,
        "comparedTo": "chance (MCC 0); perfect prediction is MCC 1", "direction": "none"}
    assert validate(rec) == []


def _task(pos_passed, neg_passed, sensitivity=None):
    f = {
        "outcomeClass": "negative-no-effect",
        "controls": {
            "positive": {"kind": "known-positive-task", "label": "species classification on the same spectra",
                         "observed": "MCC 0.97", "passed": pos_passed},
            "negative": {"kind": "adversarial-label", "label": "predicting plate identity, which should be unpredictable",
                         "observed": "MCC 1.0", "passed": neg_passed},
        },
    }
    if sensitivity:
        f["sensitivity"] = sensitivity
    return f


def test_adversarial_control_that_succeeds_is_a_failed_negative_control():
    """Predicting a meaningless label should be impossible. Succeeding means the data carries a confound."""
    label, reason = informativeness(_task(pos_passed=True, neg_passed=False))
    assert label == "uninformative"
    assert "negative control not clean" in reason


def test_clean_controls_but_no_sensitivity_gives_underpowered_not_controls_failed():
    """After batch correction both controls behave; what is left missing is a detection limit."""
    f = _task(pos_passed=True, neg_passed=True)
    apply_informativeness(f)
    assert f["informativeness"] == "uninformative"
    assert f["informativenessReason"] == "no sensitivity or power statement"
    assert f["outcomeClass"] == "inconclusive-underpowered"


def test_clean_controls_with_a_sensitivity_statement_is_informative():
    f = _task(pos_passed=True, neg_passed=True, sensitivity="the design resolves a species-level difference at this sample size")
    apply_informativeness(f)
    assert f["informativeness"] == "informative"
    assert f["outcomeClass"] == "negative-no-effect"


def test_refuted_is_not_subject_to_the_control_rule():
    """'We showed the earlier result was an artifact' is an affirmative demonstration, not an absence of
    evidence. It is judged on the refuting analysis, not on whether the original run carried controls."""
    f = {"outcomeClass": "refuted", "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}}}
    label, reason = informativeness(f)
    assert label == "not-applicable"
    apply_informativeness(f)
    assert f["outcomeClass"] == "refuted"      # must not be rewritten to an inconclusive class


def test_not_replicated_still_requires_controls():
    """A failure to replicate is still an absence of evidence and keeps the control requirement."""
    f = {"outcomeClass": "negative-not-replicated",
         "controls": {"positive": {"kind": "none"}, "negative": {"kind": "none"}}}
    label, _ = informativeness(f)
    assert label == "uninformative"
