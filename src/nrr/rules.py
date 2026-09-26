"""Machine-checkable rules from the NRR biology profile.

The informativeness rule (profile v0.1, section 4) says a negative is informative only if
the positive control passed, the negative control was clean, and a detection limit or a
power analysis is stated. v0.2 refines it: an *internal* positive (another arm of the same
experiment with a robust effect) counts as a passed positive control, and an *absent*
positive control is reported distinctly from a failed one.
"""
from __future__ import annotations

NEGATIVE_PREFIXES = ("negative-", "refuted")


def _is_negative(outcome: str) -> bool:
    return outcome.startswith(NEGATIVE_PREFIXES) or outcome.startswith("inconclusive")


def informativeness(finding: dict) -> tuple[str, str]:
    """Classify a finding as informative / uninformative / not-applicable, with the reason."""
    outcome = finding.get("outcomeClass", "")
    if not _is_negative(outcome):
        return "not-applicable", "rule applies to negative and inconclusive findings only"
    controls = finding.get("controls") or {}
    pos = controls.get("positive") or {"kind": "none"}
    neg = controls.get("negative") or {"kind": "none"}
    reasons: list[str] = []
    pos_kind = pos.get("kind", "none")
    if pos_kind == "none":
        reasons.append("no positive control")
    elif not pos.get("passed"):
        reasons.append("positive control failed")
    if neg.get("kind", "none") == "none":
        reasons.append("no negative control")
    elif not neg.get("passed"):
        reasons.append("negative control not clean")
    if not (finding.get("sensitivity") or finding.get("power")):
        reasons.append("no sensitivity or power statement")
    if reasons:
        return "uninformative", "; ".join(reasons)
    basis = "internal positive arm" if pos_kind == "internal-positive" else "designated positive control"
    return "informative", f"{basis} passed; negative control clean; sensitivity or power stated"


def enforce_outcome(finding: dict) -> list[str]:
    """An uninformative finding must carry an inconclusive outcome class (evidence of absence rule)."""
    problems = []
    label = finding.get("informativeness")
    outcome = finding.get("outcomeClass", "")
    if label == "uninformative" and not outcome.startswith("inconclusive"):
        problems.append(
            f"uninformative finding carries outcome class '{outcome}'; must be an inconclusive-* class"
        )
    if label == "informative" and outcome.startswith("inconclusive"):
        problems.append(f"informative finding carries inconclusive outcome class '{outcome}'")
    return problems


def apply_informativeness(finding: dict) -> dict:
    """Set `informativeness` and `informativenessReason` on a finding and, when the finding is an
    uninformative negative, remap its outcome class to the matching inconclusive class so that
    `enforce_outcome` holds. Positive and partial findings are left untouched."""
    label, reason = informativeness(finding)
    finding["informativeness"] = label
    finding["informativenessReason"] = reason
    if label == "uninformative" and not finding.get("outcomeClass", "").startswith("inconclusive"):
        if "no positive control" in reason:
            finding["outcomeClass"] = "inconclusive-no-positive-control"
        elif "control" in reason:
            finding["outcomeClass"] = "inconclusive-controls-failed"
        else:
            finding["outcomeClass"] = "inconclusive-underpowered"
    return finding
