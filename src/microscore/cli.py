"""Command-line interface for MicroScore experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from .audit import run_audit
from .modeling import DEFAULT_DATA_PATH, results_table, run_experiment


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

    return 0
