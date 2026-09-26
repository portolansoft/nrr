from nrr.rules import enforce_outcome, informativeness


def finding(pos_kind="designated", pos_passed=True, neg_kind="vehicle", neg_passed=True, sensitivity="stated", power=None, outcome="negative-no-effect"):
    f = {
        "outcomeClass": outcome,
        "controls": {
            "positive": {"kind": pos_kind, "passed": pos_passed} if pos_kind != "none" else {"kind": "none"},
            "negative": {"kind": neg_kind, "passed": neg_passed} if neg_kind != "none" else {"kind": "none"},
        },
    }
    if sensitivity:
        f["sensitivity"] = sensitivity
    if power:
        f["power"] = power
    return f


def test_all_conditions_met_is_informative():
    label, reason = informativeness(finding())
    assert label == "informative"


def test_failed_designated_positive_control_is_uninformative():
    label, reason = informativeness(finding(pos_passed=False))
    assert label == "uninformative"
    assert "positive control" in reason


def test_internal_positive_counts_as_passed_positive_control():
    label, reason = informativeness(finding(pos_kind="internal-positive"))
    assert label == "informative"
    assert "internal" in reason


def test_absent_positive_control_is_uninformative():
    label, reason = informativeness(finding(pos_kind="none"))
    assert label == "uninformative"
    assert "no positive control" in reason


def test_dirty_negative_control_is_uninformative():
    label, _ = informativeness(finding(neg_passed=False))
    assert label == "uninformative"


def test_missing_sensitivity_and_power_is_uninformative():
    label, reason = informativeness(finding(sensitivity=None))
    assert label == "uninformative"
    assert "sensitivity" in reason


def test_power_alone_satisfies_sensitivity_requirement():
    label, _ = informativeness(finding(sensitivity=None, power="80% for d=0.4"))
    assert label == "informative"


def test_positive_findings_are_not_subject_to_the_rule():
    label, reason = informativeness(finding(pos_kind="none", outcome="positive"))
    assert label == "not-applicable"


def test_enforce_outcome_flags_negative_class_on_uninformative_finding():
    f = finding(pos_kind="none")
    f["informativeness"] = "uninformative"
    assert enforce_outcome(f)


def test_enforce_outcome_accepts_inconclusive_class_on_uninformative_finding():
    f = finding(pos_kind="none", outcome="inconclusive-no-positive-control")
    f["informativeness"] = "uninformative"
    assert enforce_outcome(f) == []


from nrr.rules import apply_informativeness


def test_apply_informativeness_remaps_failed_control_to_inconclusive():
    f = finding(pos_passed=False)
    apply_informativeness(f)
    assert f["informativeness"] == "uninformative"
    assert f["outcomeClass"] == "inconclusive-controls-failed"
    assert enforce_outcome(f) == []


def test_apply_informativeness_remaps_absent_control_to_no_positive_control_class():
    f = finding(pos_kind="none")
    apply_informativeness(f)
    assert f["outcomeClass"] == "inconclusive-no-positive-control"


def test_apply_informativeness_remaps_missing_sensitivity_to_underpowered():
    f = finding(sensitivity=None)
    apply_informativeness(f)
    assert f["outcomeClass"] == "inconclusive-underpowered"


def test_apply_informativeness_leaves_informative_and_positive_findings_alone():
    f = finding()
    apply_informativeness(f)
    assert f["outcomeClass"] == "negative-no-effect" and f["informativeness"] == "informative"
    g = finding(pos_kind="none", outcome="positive")
    apply_informativeness(g)
    assert g["outcomeClass"] == "positive" and g["informativeness"] == "not-applicable"
