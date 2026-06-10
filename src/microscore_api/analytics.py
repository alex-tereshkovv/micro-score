"""Live analytics helpers for the MicroScore API prototype."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from microscore.policy import ThresholdPolicy, default_threshold_policies

POLICY_SEGMENT_FEATURES: tuple[str, ...] = (
    "settlement_type",
    "pavlodar_district",
    "gender",
    "employment_status",
)

PREDICTED_HIGH_RISK_THRESHOLD = 0.65


def _score_probability(application: dict[str, Any]) -> float | None:
    score_result = application.get("score_result")
    if not score_result:
        return None
    probability = score_result.get("high_risk_probability")
    if probability is None:
        return None
    return float(probability)


def _policy_action(probability: float, policy: ThresholdPolicy) -> str:
    if probability <= policy.approve_threshold:
        return "approve"
    if probability >= policy.decline_threshold:
        return "decline"
    return "review"


def _safe_rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return count / total


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _segment_value(application: dict[str, Any], feature: str) -> str:
    signals = application.get("behavioral_signals") or {}
    if feature == "settlement_type":
        value = application.get("settlement_type") or signals.get("settlement_type")
    elif feature == "pavlodar_district":
        value = application.get("district") or signals.get("pavlodar_district")
    else:
        value = signals.get(feature)
    return str(value or "unknown")


def _scored_applications(applications: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        application
        for application in applications
        if _score_probability(application) is not None
    ]


def policy_analytics(
    applications: Iterable[dict[str, Any]],
    *,
    policies: tuple[ThresholdPolicy, ...] | None = None,
    segment_features: tuple[str, ...] = POLICY_SEGMENT_FEATURES,
) -> dict[str, Any]:
    """Summarize approve/review/decline policy effects on scored applications."""

    scored = _scored_applications(applications)
    policy_set = policies or default_threshold_policies()

    policy_rows = [
        _policy_row(scored, policy)
        for policy in policy_set
    ]
    segment_rows = [
        row
        for policy in policy_set
        for row in _segment_rows(scored, policy, segment_features)
    ]

    return {
        "scored_application_count": len(scored),
        "policies": policy_rows,
        "segments": segment_rows,
        "note": (
            "Live policy analytics use predicted probabilities only; repayment "
            "outcomes are not available in the demo database."
        ),
    }


def _policy_row(applications: list[dict[str, Any]], policy: ThresholdPolicy) -> dict[str, Any]:
    probabilities = [
        probability
        for application in applications
        if (probability := _score_probability(application)) is not None
    ]
    actions = [_policy_action(probability, policy) for probability in probabilities]
    approved_probabilities = [
        probability
        for probability, action in zip(probabilities, actions)
        if action == "approve"
    ]
    review_probabilities = [
        probability
        for probability, action in zip(probabilities, actions)
        if action == "review"
    ]
    declined_probabilities = [
        probability
        for probability, action in zip(probabilities, actions)
        if action == "decline"
    ]
    n = len(probabilities)
    auto_approve_count = actions.count("approve")
    manual_review_count = actions.count("review")
    auto_decline_count = actions.count("decline")
    predicted_high_risk_auto_approved_count = sum(
        probability >= PREDICTED_HIGH_RISK_THRESHOLD
        for probability in approved_probabilities
    )

    return {
        "policy": policy.name,
        "description": policy.description,
        "approve_threshold": policy.approve_threshold,
        "decline_threshold": policy.decline_threshold,
        "n": n,
        "auto_approve_count": auto_approve_count,
        "manual_review_count": manual_review_count,
        "auto_decline_count": auto_decline_count,
        "auto_approval_rate": _safe_rate(auto_approve_count, n),
        "manual_review_rate": _safe_rate(manual_review_count, n),
        "auto_decline_rate": _safe_rate(auto_decline_count, n),
        "mean_high_risk_probability": _mean(probabilities),
        "mean_approved_probability": _mean(approved_probabilities),
        "mean_review_probability": _mean(review_probabilities),
        "mean_declined_probability": _mean(declined_probabilities),
        "predicted_high_risk_auto_approved_count": predicted_high_risk_auto_approved_count,
        "predicted_high_risk_auto_approval_rate": _safe_rate(
            predicted_high_risk_auto_approved_count,
            n,
        ),
    }


def _segment_rows(
    applications: list[dict[str, Any]],
    policy: ThresholdPolicy,
    segment_features: tuple[str, ...],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[tuple[float, str]]] = {}
    for application in applications:
        probability = _score_probability(application)
        if probability is None:
            continue
        action = _policy_action(probability, policy)
        for feature in segment_features:
            groups.setdefault(
                (feature, _segment_value(application, feature)),
                [],
            ).append((probability, action))

    rows: list[dict[str, Any]] = []
    for (feature, value), items in sorted(groups.items()):
        probabilities = [probability for probability, _action in items]
        actions = [action for _probability, action in items]
        n = len(items)
        rows.append(
            {
                "policy": policy.name,
                "segment_feature": feature,
                "segment_value": value,
                "n": n,
                "auto_approval_rate": _safe_rate(actions.count("approve"), n),
                "manual_review_rate": _safe_rate(actions.count("review"), n),
                "auto_decline_rate": _safe_rate(actions.count("decline"), n),
                "mean_high_risk_probability": _mean(probabilities),
                "predicted_high_risk_share": _safe_rate(
                    sum(
                        probability >= PREDICTED_HIGH_RISK_THRESHOLD
                        for probability in probabilities
                    ),
                    n,
                ),
            }
        )
    return rows
