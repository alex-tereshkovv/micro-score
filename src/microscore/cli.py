"""Command-line interface for MicroScore experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from .ablation import run_ablation_study
from .audit import run_audit
from .benchmark import (
    DEFAULT_BENCHMARK_REPORTS_DIR,
    DEFAULT_UCI_DEFAULT_DATA_PATH,
    run_uci_default_benchmark,
)
from .decision import run_decision_analysis
from .error_analysis import run_error_analysis
from .modeling import (
    DEFAULT_DATA_PATH,
    load_dataset,
    results_table,
    run_experiment,
    run_experiment_on_frame,
)
from .policy import run_policy_analysis
from .reporting import DEFAULT_REPORTS_DIR, generate_research_artifacts
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
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run feature-group ablation study across proxy, behavioral, and regional scenarios.",
    )
    parser.add_argument(
        "--error-analysis",
        action="store_true",
        help="Run false-positive and false-negative analysis on the held-out test set.",
    )
    parser.add_argument(
        "--policy-analysis",
        action="store_true",
        help="Compare approve/review/decline threshold policies.",
    )
    parser.add_argument(
        "--reports",
        action="store_true",
        help="Generate reproducible research artifacts under reports/research-artifacts.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Directory for generated research artifacts.",
    )
    parser.add_argument(
        "--benchmark",
        choices=("uci-default",),
        help="Run a public benchmark experiment instead of the synthetic MicroScore dataset.",
    )
    parser.add_argument(
        "--benchmark-data",
        type=Path,
        default=DEFAULT_UCI_DEFAULT_DATA_PATH,
        help="Path to the local UCI Default of Credit Card Clients CSV/XLS file.",
    )
    parser.add_argument(
        "--benchmark-reports-dir",
        type=Path,
        default=DEFAULT_BENCHMARK_REPORTS_DIR,
        help="Directory for generated public benchmark artifacts.",
    )
    return parser.parse_args()


def _print_artifact_paths(paths: tuple[Path, ...]) -> None:
    print("\nResearch artifacts written")
    for path in paths:
        print(path)


def main() -> int:
    args = parse_args()

    if args.benchmark == "uci-default":
        artifacts = run_uci_default_benchmark(
            args.benchmark_data,
            output_dir=args.benchmark_reports_dir,
        )
        print("\nBenchmark artifacts written")
        for path in artifacts.files:
            print(path)
        return 0

    if args.reports and not any(
        (
            args.audit,
            args.regional,
            args.decision,
            args.ablation,
            args.error_analysis,
            args.policy_analysis,
        )
    ):
        artifacts = generate_research_artifacts(
            args.data,
            output_dir=args.reports_dir,
        )
        _print_artifact_paths(artifacts.files)
        return 0

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

    if args.ablation:
        ablation = run_ablation_study(args.data)
        columns = [
            "scenario",
            "model",
            "feature_count",
            "uses_regional_context",
            "includes_late_payment_count",
            "includes_leakage_columns",
            "test_roc_auc",
            "test_brier_score",
            "test_f1",
            "delta_test_roc_auc_vs_no_leakage",
            "delta_test_brier_score_vs_no_leakage",
        ]

        print("\nFeature-group ablation study")
        print(ablation[columns].round(4).to_string(index=False))

    if args.error_analysis:
        errors = run_error_analysis(args.data)
        summary_columns = [
            "error_type",
            "n",
            "share_of_test",
            "mean_high_risk_probability",
            "mean_late_payment_count",
            "decision_meaning",
        ]
        segment_columns = [
            "segment_feature",
            "segment_value",
            "n",
            "false_positive_rate",
            "false_negative_rate",
        ]
        example_columns = [
            "row_index",
            "actual_credit_risk",
            "predicted_credit_risk",
            "high_risk_probability",
            "late_payment_count",
            "annual_income",
            "loan_application_amount",
        ]

        print("\nError analysis summary")
        print(
            errors.summary[errors.summary["error_type"].notna()][summary_columns]
            .round(4)
            .to_string(index=False)
        )

        print("\nSegment error preview")
        print(errors.segment_errors[segment_columns].round(4).head(12).to_string(index=False))

        print("\nFalse positive examples")
        print(
            errors.false_positive_examples[
                [column for column in example_columns if column in errors.false_positive_examples.columns]
            ]
            .round(4)
            .head(8)
            .to_string(index=False)
        )

        print("\nFalse negative examples")
        print(
            errors.false_negative_examples[
                [column for column in example_columns if column in errors.false_negative_examples.columns]
            ]
            .round(4)
            .head(8)
            .to_string(index=False)
        )

    if args.policy_analysis:
        policies = run_policy_analysis(args.data)
        policy_columns = [
            "policy",
            "auto_approval_rate",
            "manual_review_rate",
            "auto_decline_rate",
            "high_risk_rate_among_approved",
            "high_risk_approval_rate",
            "good_borrower_auto_decline_rate",
            "expected_profit_per_applicant",
        ]
        segment_columns = [
            "policy",
            "segment_feature",
            "segment_value",
            "n",
            "auto_approval_rate",
            "manual_review_rate",
            "auto_decline_rate",
        ]

        print("\nThreshold policy analysis")
        print(policies.policy_table[policy_columns].round(4).to_string(index=False))

        print("\nSegment policy preview")
        print(
            policies.segment_policy_table[segment_columns]
            .round(4)
            .head(16)
            .to_string(index=False)
        )

    if args.reports:
        artifacts = generate_research_artifacts(
            args.data,
            output_dir=args.reports_dir,
        )
        _print_artifact_paths(artifacts.files)

    return 0
