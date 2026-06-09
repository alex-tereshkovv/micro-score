"""Command-line interface for MicroScore experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from .audit import run_audit
from .decision import run_decision_analysis
from .modeling import DEFAULT_DATA_PATH, load_dataset, results_table, run_experiment, run_experiment_on_frame
from .regional import add_pavlodar_regional_context, regional_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate MicroScore models.")
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Path to credit_risk_dataset.csv.",
    )
    parser.add_argument(
        "--top-features",
        type=int,
        default=12,
        help="Number of top features to print for each model.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run proxy-feature and segment/fairness audit tables.",
    )
    parser.add_argument(
        "--regional",
        action="store_true",
        help="Add simulated Pavlodar-region context and compare regional model results.",
    )
    parser.add_argument(
        "--decision",
        action="store_true",
        help="Run threshold-based loan approval and expected-loss analysis.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = run_experiment(args.data)

    print("\nModel comparison")
    print(results_table(results).round(4).to_string(index=False))

    for result in results:
        print(f"\nTop features: {result.name}")
        print(result.feature_importance.head(args.top_features).round(4).to_string(index=False))
        print(f"\nConfusion matrix: {result.name}")
        print(result.confusion_matrix)

    if args.audit:
        audit = run_audit(args.data)

        print("\nProxy audit")
        print(audit.proxy_summary.round(4).to_string(index=False))

        print("\nHigh-risk rate by late_payment_count")
        print(audit.proxy_by_value.round(4).to_string(index=False))

        print("\nModel sensitivity to dropping late_payment_count")
        sensitivity_columns = [
            "scenario",
            "model",
            "test_accuracy",
            "test_roc_auc",
            "test_precision",
            "test_recall",
            "test_f1",
            "delta_test_roc_auc",
            "delta_test_recall",
            "delta_test_f1",
        ]
        print(
            audit.feature_drop_comparison[sensitivity_columns]
            .round(4)
            .to_string(index=False)
        )

        print("\nSegment metrics")
        print(audit.segment_metrics.round(4).to_string(index=False))

    if args.regional or args.decision:
        regional_frame = add_pavlodar_regional_context(load_dataset(args.data))

    if args.regional:
        print("\nPavlodar regional simulation summary")
        print(regional_summary(regional_frame).round(4).to_string(index=False))

        regional_results = run_experiment_on_frame(regional_frame)
        print("\nModel comparison with simulated Pavlodar regional context")
        print(results_table(regional_results).round(4).to_string(index=False))

    if args.decision:
        decision = run_decision_analysis(regional_frame)

        print("\nDecision model quality")
        print(decision.model_quality.round(4).to_string(index=False))

        print("\nProfit-optimal threshold")
        print(decision.profit_optimal_metrics.round(4).to_string(index=False))

        print("\nSelected threshold with minimum approval-rate constraint")
        print(decision.best_threshold_metrics.round(4).to_string(index=False))

        print("\nThreshold decision table")
        print(decision.threshold_table.round(4).to_string(index=False))

        print("\nSegment approval at best threshold")
        print(decision.segment_approval.round(4).to_string(index=False))

    return 0
