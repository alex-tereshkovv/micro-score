from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "reports" / "submission" / "technical-defense.json"
GUIDE_PATH = PROJECT_ROOT / "docs" / "TECHNICAL_INTERVIEW_GUIDE.md"
SCHEMA_VERSION = "microscore-technical-defense-v1"


HEADLINE_CLAIMS = (
    {
        "key": "synthetic_logistic_regression_roc_auc",
        "value": 0.806,
        "evidence_class": "synthetic_experiment",
        "source": "reports/research-artifacts/model_metrics.csv",
    },
    {
        "key": "synthetic_random_forest_roc_auc",
        "value": 0.830,
        "evidence_class": "synthetic_experiment",
        "source": "reports/research-artifacts/model_metrics.csv",
    },
    {
        "key": "random_forest_without_late_payment_count_roc_auc",
        "value": 0.492,
        "evidence_class": "synthetic_ablation",
        "source": "reports/research-artifacts/ablation_study.csv",
    },
    {
        "key": "ten_split_random_forest_without_late_payment_count_mean_roc_auc",
        "value": 0.501,
        "evidence_class": "synthetic_robustness",
        "source": "reports/research-artifacts/robustness_summary.csv",
    },
    {
        "key": "uci_random_forest_roc_auc",
        "value": 0.775,
        "evidence_class": "public_benchmark_not_local_validation",
        "source": "reports/benchmark-artifacts/uci-default-credit-card-clients/model_metrics.csv",
    },
)


QUESTIONS = (
    {
        "id": "model-choice",
        "category": "modeling",
        "question": "Why use Logistic Regression when Random Forest scores higher?",
        "target_seconds": 60,
        "short_answer": (
            "Logistic Regression is an interpretable probability baseline for a binary "
            "outcome. Random Forest is a nonlinear comparison, but a small ROC-AUC gain "
            "does not outweigh evidence quality, calibration, and explanation cost."
        ),
        "must_cover": [
            "binary probability output",
            "preprocessing pipeline and balanced classes",
            "interpretability is conditional, not causal",
        ],
        "evidence": [
            "src/microscore/modeling.py",
            "src/microscore_api/scoring.py",
            "docs/MODEL_CARD.md",
        ],
        "follow_up": "What assumption makes a Logistic Regression coefficient unsafe to read causally?",
        "do_not_claim": "That Logistic Regression is inherently fair or causal.",
    },
    {
        "id": "roc-auc",
        "category": "evaluation",
        "question": "What does ROC-AUC measure, and what does it miss?",
        "target_seconds": 60,
        "short_answer": (
            "ROC-AUC measures ranking: how often a positive case receives a higher "
            "score than a negative case. It does not select a threshold, prove "
            "calibration, price errors, or establish fairness or external validity."
        ),
        "must_cover": [
            "0.5 is chance ranking",
            "ranking is different from calibration",
            "policy and error costs require separate analysis",
        ],
        "evidence": [
            "src/microscore/modeling.py",
            "src/microscore/error_analysis.py",
            "reports/research-artifacts/model_metrics.csv",
        ],
        "follow_up": "Why can a useful ROC-AUC coexist with unsafe probabilities?",
        "do_not_claim": "That ROC-AUC alone proves a model is useful for lending.",
    },
    {
        "id": "proxy-risk",
        "category": "data-quality",
        "question": "Why is late_payment_count the central problem?",
        "target_seconds": 75,
        "short_answer": (
            "The feature nearly carries the synthetic result by itself. Removing it "
            "drops Random Forest ROC-AUC from about 0.830 to 0.492, so the remaining "
            "signals do not support the intended thin-file claim."
        ),
        "must_cover": [
            "repayment history is not genuinely new alternative data",
            "the feature may proxy access to prior formal credit",
            "report and monitor the dependence instead of hiding it",
        ],
        "evidence": [
            "src/microscore/audit.py",
            "src/microscore/ablation.py",
            "docs/PROXY_FEATURE_MONITORING.md",
            "reports/research-artifacts/ablation_study.csv",
        ],
        "follow_up": "Why not simply delete the feature and report the full-model score?",
        "do_not_claim": "That the feature is always illegal, causal, or unusable in every context.",
    },
    {
        "id": "ablation",
        "category": "evaluation",
        "question": "What does the ablation study prove and not prove?",
        "target_seconds": 75,
        "short_answer": (
            "Retraining without a feature or group measures dependence on that "
            "information. Here it exposes near-chance thin-file performance; it does "
            "not prove the remaining variables have no value in every real dataset."
        ),
        "must_cover": [
            "retrain rather than only mask an input",
            "compare held-out metrics against the leakage-safe baseline",
            "interpret a negative result without generalizing beyond the dataset",
        ],
        "evidence": [
            "src/microscore/ablation.py",
            "src/microscore/reporting.py",
            "reports/research-artifacts/ablation_study.csv",
        ],
        "follow_up": "How did repeated splits change your confidence in this result?",
        "do_not_claim": "That one ablation establishes universal feature uselessness.",
    },
    {
        "id": "robustness",
        "category": "evaluation",
        "question": "How do you know the negative ablation is not one lucky split?",
        "target_seconds": 75,
        "short_answer": (
            "Ten stratified splits, a 1,000-resample bootstrap on the held-out sample, "
            "and deterministic shift tests preserve the core result. The ten-split "
            "no-late-payment Random Forest mean ROC-AUC is about 0.501."
        ),
        "must_cover": [
            "repeated-split stability",
            "bootstrap uncertainty",
            "stress tests are not temporal or external validation",
        ],
        "evidence": [
            "src/microscore/robustness.py",
            "docs/ROBUSTNESS_AND_UNCERTAINTY.md",
            "reports/research-artifacts/robustness_summary.csv",
        ],
        "follow_up": "What validation gap still remains after bootstrap and shift tests?",
        "do_not_claim": "That synthetic resampling replaces temporal or external validation.",
    },
    {
        "id": "threshold-policy",
        "category": "decision-policy",
        "question": "Why use two thresholds and a review band?",
        "target_seconds": 60,
        "short_answer": (
            "A probability is not a decision. Two thresholds create approve, review, "
            "and decline zones so policy owners can expose the trade-off between access, "
            "risk, and analyst capacity instead of hiding it in one cutoff."
        ),
        "must_cover": [
            "probability, risk band, and policy action are different",
            "review workload is a real operational cost",
            "thresholds require validated costs and probabilities",
        ],
        "evidence": [
            "src/microscore/policy.py",
            "src/microscore/decision.py",
            "reports/research-artifacts/policy_analysis.csv",
        ],
        "follow_up": "Who should own the threshold choice in a real pilot?",
        "do_not_claim": "That the demo thresholds are optimal for a real MFI.",
    },
    {
        "id": "monte-carlo",
        "category": "uncertainty",
        "question": "What does Monte Carlo add to the deterministic policy table?",
        "target_seconds": 75,
        "short_answer": (
            "It propagates shared macro and application-level calibration uncertainty "
            "into a distribution of portfolio outcomes. Paired scenarios use common "
            "random numbers, making scenario differences more stable and reproducible."
        ),
        "must_cover": [
            "portfolio scenarios do not rescore an individual borrower",
            "correlated macro shock and residual application shock",
            "seed, assumptions, model version, and fingerprint are recorded",
        ],
        "evidence": [
            "src/microscore_api/simulation.py",
            "docs/MONTE_CARLO_METHODOLOGY.md",
            "tests/test_api_simulation.py",
        ],
        "follow_up": "Why are the outputs scenario ranges rather than forecasts or regulatory VaR?",
        "do_not_claim": "That synthetic assumptions produce calibrated KZT forecasts.",
    },
    {
        "id": "system-path",
        "category": "architecture",
        "question": "Trace one application from the browser through the API and database.",
        "target_seconds": 90,
        "short_answer": (
            "The frontend submits a typed payload; FastAPI validates identity, role, "
            "tenant, and lifecycle rules; the repository persists the application; "
            "scoring records probability, explanation, model provenance, and audit events."
        ),
        "must_cover": [
            "browser demo mode is separate from the real FastAPI runtime",
            "Pydantic validation and route authorization",
            "repository persistence, scoring provenance, and audit trail",
        ],
        "evidence": [
            "apps/web/app.js",
            "src/microscore_api/schemas.py",
            "src/microscore_api/main.py",
            "src/microscore_api/database.py",
            "docs/ARCHITECTURE.md",
        ],
        "follow_up": "What does the public browser demo prove, and what does it not prove?",
        "do_not_claim": "That GitHub Pages is connected to production borrower data.",
    },
    {
        "id": "postgres-boundary",
        "category": "architecture",
        "question": "Why keep SQLite, and what exactly is proven about PostgreSQL?",
        "target_seconds": 75,
        "short_answer": (
            "SQLite keeps local review reproducible. PostgreSQL implements the same "
            "52-method repository contract and is exercised by disposable migration, "
            "live HTTP, container, and backup/restore fingerprint gates."
        ),
        "must_cover": [
            "local convenience versus deployment candidate",
            "repository contract parity",
            "managed operations and high availability remain incomplete",
        ],
        "evidence": [
            "src/microscore_api/postgres_repository.py",
            "scripts/postgresql-runtime-smoke.py",
            "scripts/postgresql-backup-restore-smoke.py",
            "docs/POSTGRESQL_RECOVERY.md",
        ],
        "follow_up": "What production database claims are still blocked?",
        "do_not_claim": "That disposable PostgreSQL CI proves production operations or availability.",
    },
    {
        "id": "human-review",
        "category": "governance",
        "question": "Why is human review necessary, and why is it not sufficient?",
        "target_seconds": 60,
        "short_answer": (
            "Synthetic evidence and uncertain policy choices make automated lending "
            "unjustified. Human review adds accountable judgment, but reviewers can "
            "still introduce bias or rubber-stamp, so decisions and overrides are audited."
        ),
        "must_cover": [
            "decision support rather than automatic lending",
            "human bias and automation bias",
            "decision history, provenance, and lifecycle locks",
        ],
        "evidence": [
            "docs/MODEL_CARD.md",
            "src/microscore_api/analytics.py",
            "tests/test_api_integration.py",
        ],
        "follow_up": "What evidence would justify narrowing the human review band?",
        "do_not_claim": "That a human in the loop automatically makes the system fair or safe.",
    },
    {
        "id": "external-validity",
        "category": "research-boundary",
        "question": "What is the strongest claim the project can honestly make?",
        "target_seconds": 60,
        "short_answer": (
            "It is a reproducible research and decision-support prototype that exposes "
            "a dominant synthetic proxy, connects evidence to review workflows, and "
            "makes pre-pilot blockers visible. It is not validated for real lending."
        ),
        "must_cover": [
            "synthetic experiment versus public benchmark",
            "UCI transfer checks the pipeline, not Kazakhstan validity",
            "real borrower data and production lending stay blocked",
        ],
        "evidence": [
            "docs/DATA_STATEMENT.md",
            "docs/RELEASE_CANDIDATE.md",
            "reports/benchmark-artifacts/uci-default-credit-card-clients/SUMMARY.md",
        ],
        "follow_up": "Why does the UCI benchmark strengthen engineering confidence but not local validity?",
        "do_not_claim": "That public benchmark performance validates Pavlodar borrowers.",
    },
    {
        "id": "pilot-plan",
        "category": "research-boundary",
        "question": "What would you do first with real pilot data?",
        "target_seconds": 75,
        "short_answer": (
            "Define the target and observation window with the MFI, minimize and separate "
            "identifiers, use temporal and geographic validation, repeat proxy and "
            "calibration analysis, then set policy only from observed costs and outcomes."
        ),
        "must_cover": [
            "target definition before modeling",
            "consent, minimization, and temporal validation",
            "monitoring, appeals, overrides, and security review",
        ],
        "evidence": [
            "docs/DATA_STATEMENT.md",
            "docs/MODEL_CARD.md",
            "docs/PILOT_DATA_SCHEMA.md",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "follow_up": "Which result would make you stop rather than deploy?",
        "do_not_claim": "That the existing model can be deployed before local validation.",
    },
)


REQUIRED_GUIDE_SECTIONS = (
    "## 1. Why Logistic Regression?",
    "## 2. What Does ROC-AUC Mean?",
    "## 3. Why Is `late_payment_count` A Problem?",
    "## 4. What Does Ablation Show?",
    "## 6. Why Threshold Policies Instead Of One Cutoff?",
    "## 7. What Does Monte Carlo Add?",
    "## 8. How Do Frontend, API, And Database Fit Together?",
    "## Ownership Check",
)


def _csv_rows(relative_path: str) -> list[dict[str, str]]:
    with (PROJECT_ROOT / relative_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _find_metric(
    relative_path: str,
    *,
    model: str,
    metric: str,
    scenario: str | None = None,
) -> float:
    for row in _csv_rows(relative_path):
        if row.get("model") != model:
            continue
        if scenario is not None and row.get("scenario") != scenario:
            continue
        return float(row[metric])
    raise AssertionError(
        f"Metric row not found in {relative_path}: model={model}, scenario={scenario}"
    )


def validate_sources() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    for section in REQUIRED_GUIDE_SECTIONS:
        if section not in guide:
            raise AssertionError(f"Technical interview guide is missing section: {section}")

    ids = [question["id"] for question in QUESTIONS]
    if len(ids) != len(set(ids)):
        raise AssertionError("Technical defense question ids must be unique.")
    for question in QUESTIONS:
        for relative_path in question["evidence"]:
            if not (PROJECT_ROOT / relative_path).is_file():
                raise FileNotFoundError(
                    f"Technical defense evidence is missing: {relative_path}"
                )

    measured = {
        "synthetic_logistic_regression_roc_auc": _find_metric(
            "reports/research-artifacts/model_metrics.csv",
            model="Logistic Regression",
            metric="test_roc_auc",
        ),
        "synthetic_random_forest_roc_auc": _find_metric(
            "reports/research-artifacts/model_metrics.csv",
            model="Random Forest",
            metric="test_roc_auc",
        ),
        "random_forest_without_late_payment_count_roc_auc": _find_metric(
            "reports/research-artifacts/ablation_study.csv",
            model="Random Forest",
            scenario="no_late_payment_count",
            metric="test_roc_auc",
        ),
        "ten_split_random_forest_without_late_payment_count_mean_roc_auc": _find_metric(
            "reports/research-artifacts/robustness_summary.csv",
            model="Random Forest",
            scenario="no_late_payment_count",
            metric="roc_auc_mean",
        ),
        "uci_random_forest_roc_auc": _find_metric(
            "reports/benchmark-artifacts/uci-default-credit-card-clients/model_metrics.csv",
            model="Random Forest",
            metric="test_roc_auc",
        ),
    }
    for claim in HEADLINE_CLAIMS:
        actual = round(measured[claim["key"]], 3)
        if actual != claim["value"]:
            raise AssertionError(
                f"Defense claim drift for {claim['key']}: expected {claim['value']}, got {actual}"
            )


def build_packet() -> dict[str, Any]:
    validate_sources()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "owner_rehearsal_required",
        "automated_gate_scope": (
            "This check proves question coverage, evidence-path existence, metric "
            "consistency, and deterministic serialization. It cannot prove oral understanding."
        ),
        "manual_pass_rule": (
            "Answer every core question in your own words, state at least one limitation, "
            "open one cited artifact, and survive the follow-up without a prohibited claim."
        ),
        "timed_routes": [
            {
                "name": "60-second overview",
                "seconds": 60,
                "question_ids": ["external-validity", "proxy-risk", "system-path"],
            },
            {
                "name": "5-minute technical defense",
                "seconds": 300,
                "question_ids": [
                    "model-choice",
                    "roc-auc",
                    "proxy-risk",
                    "ablation",
                    "threshold-policy",
                    "system-path",
                ],
            },
            {
                "name": "15-minute deep defense",
                "seconds": 900,
                "question_ids": [question["id"] for question in QUESTIONS],
            },
        ],
        "scorecard": {
            "dimensions": [
                "plain-language correctness",
                "evidence navigation",
                "limitations and uncertainty",
                "follow-up reasoning",
            ],
            "scale": {"0": "unsupported", "1": "partial", "2": "defensible"},
            "pass": "At least 7/8 per question, with no zero and no prohibited claim.",
        },
        "headline_claims": list(HEADLINE_CLAIMS),
        "questions": list(QUESTIONS),
    }


def serialized_packet() -> str:
    return json.dumps(build_packet(), indent=2, sort_keys=True) + "\n"


def write_packet() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(serialized_packet(), encoding="utf-8")


def check_packet() -> None:
    if not OUTPUT_PATH.is_file():
        raise AssertionError(
            "Technical defense packet is missing. Run build-technical-defense-packet.py --write."
        )
    if OUTPUT_PATH.read_text(encoding="utf-8") != serialized_packet():
        raise AssertionError(
            "Technical defense packet is stale. Rebuild it after evidence or claims change."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify the deterministic MicroScore technical defense packet."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.write:
            write_packet()
            action = "written"
        else:
            check_packet()
            action = "verified"
    except (AssertionError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"::error title=Technical defense check failed::{exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "mode": "technical-defense",
                "action": action,
                "questions": len(QUESTIONS),
                "headline_claims": len(HEADLINE_CLAIMS),
                "oral_understanding_verified": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
