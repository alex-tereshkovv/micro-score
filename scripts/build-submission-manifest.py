from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "reports" / "submission" / "manifest.json"
RELEASE_LABEL = "release-candidate-v1"
RELEASE_DATE = "2026-10-19"
EXPECTED_TEST_COUNT = 152
EXPECTED_SMOKE_WORKFLOWS = 13

CRITICAL_ARTIFACTS = (
    ".github/workflows/ci.yml",
    "README.md",
    "apps/web/evidence.html",
    "apps/web/index.html",
    "apps/web/showcase.html",
    "docs/DATA_STATEMENT.md",
    "docs/ENGINEERING_QUALITY.md",
    "docs/MODEL_CARD.md",
    "docs/OBSERVABILITY_AND_PERFORMANCE.md",
    "docs/PROJECT_BRIEF.md",
    "docs/RELEASE_CANDIDATE.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RESEARCH_PAPER.md",
    "output/pdf/MicroScore_Engineering_Case_Study.pdf",
    "output/pdf/MicroScore_Research_Paper.pdf",
    "reports/benchmark-artifacts/uci-default-credit-card-clients/model_metrics.csv",
    "reports/research-artifacts/manifest.json",
    "reports/research-artifacts/robustness_summary.csv",
    "scripts/build-submission-manifest.py",
    "scripts/check.ps1",
    "tests/test_submission_readiness.py",
)


def canonical_artifact_bytes(path: Path) -> tuple[bytes, str]:
    content = path.read_bytes()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content, "binary"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return normalized, "utf8_lf"


def artifact_record(relative_path: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Required submission artifact is missing: {relative_path}")
    content, hash_mode = canonical_artifact_bytes(path)
    return {
        "path": relative_path,
        "bytes": len(content),
        "hash_mode": hash_mode,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": "microscore-submission-manifest-v1",
        "release_label": RELEASE_LABEL,
        "release_date": RELEASE_DATE,
        "status": "review_ready_not_production_ready",
        "quality_gate": {
            "python_tests": EXPECTED_TEST_COUNT,
            "local_smoke_workflows": EXPECTED_SMOKE_WORKFLOWS,
            "postgresql_repository_methods": 52,
            "ci_jobs": [
                "test",
                "postgresql-migration",
                "observability-performance",
                "deployment-candidate",
            ],
        },
        "headline_claims": [
            {
                "key": "synthetic_logistic_regression_roc_auc",
                "value": 0.806,
                "evidence_class": "synthetic_experiment",
            },
            {
                "key": "synthetic_random_forest_roc_auc",
                "value": 0.830,
                "evidence_class": "synthetic_experiment",
            },
            {
                "key": "random_forest_without_late_payment_count_roc_auc",
                "value": 0.492,
                "evidence_class": "synthetic_ablation",
            },
            {
                "key": "ten_split_random_forest_without_late_payment_count_mean_roc_auc",
                "value": 0.501,
                "evidence_class": "synthetic_robustness",
            },
            {
                "key": "uci_random_forest_roc_auc",
                "value": 0.775,
                "evidence_class": "public_benchmark_not_local_validation",
            },
        ],
        "public_entry_points": [
            "https://alex-tereshkovv.github.io/micro-score/#/review",
            "https://alex-tereshkovv.github.io/micro-score/showcase.html",
            "https://alex-tereshkovv.github.io/micro-score/evidence.html",
        ],
        "required_limitations": [
            "No validation on real Kazakhstan MFI borrower data.",
            "Human decision support, not automatic lending.",
            "Synthetic and public-benchmark evidence do not establish production readiness.",
            "Runtime budgets are regression guards, not a production SLO or capacity claim.",
        ],
        "reproduction_commands": [
            ".venv\\Scripts\\python -m microscore --reports",
            ".venv\\Scripts\\python scripts\\build_research_paper.py",
            ".venv\\Scripts\\python scripts\\build_admissions_case_study.py",
            "powershell -ExecutionPolicy Bypass -File scripts\\check.ps1",
        ],
        "artifacts": [artifact_record(path) for path in CRITICAL_ARTIFACTS],
    }


def serialized_manifest() -> str:
    return json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n"


def write_manifest() -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(serialized_manifest(), encoding="utf-8")


def check_manifest() -> None:
    if not MANIFEST_PATH.is_file():
        raise AssertionError(
            "Submission manifest is missing. Run scripts/build-submission-manifest.py --write."
        )
    expected = serialized_manifest()
    actual = MANIFEST_PATH.read_text(encoding="utf-8")
    if actual != expected:
        raise AssertionError(
            "Submission manifest is stale. Rebuild it only after the release artifacts are final."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify the deterministic MicroScore submission manifest."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.write:
            write_manifest()
            action = "written"
        else:
            check_manifest()
            action = "verified"
    except (AssertionError, FileNotFoundError) as exc:
        print(f"::error title=Submission manifest check failed::{exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "mode": "submission-manifest",
                "action": action,
                "release_label": RELEASE_LABEL,
                "artifacts": len(CRITICAL_ARTIFACTS),
                "python_tests": EXPECTED_TEST_COUNT,
                "local_smoke_workflows": EXPECTED_SMOKE_WORKFLOWS,
                "production_ready": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
