"""MicroScore modeling utilities."""

from .ablation import AblationScenario, ablation_scenarios, run_ablation_study
from .audit import AuditReport, run_audit
from .benchmark import (
    BenchmarkArtifactPaths,
    load_uci_default_benchmark,
    normalize_uci_default_frame,
    run_uci_default_benchmark,
)
from .decision import DecisionReport, run_decision_analysis
from .error_analysis import ErrorAnalysisReport, run_error_analysis
from .explainability import LocalExplanation, LocalFactor, logistic_local_explanation
from .features import TARGET_COLUMN, add_behavioral_features, make_model_frame
from .modeling import calibration_table
from .paths import DEFAULT_DATA_PATH, PROJECT_ROOT, resolve_data_path
from .policy import PolicyAnalysisReport, ThresholdPolicy, run_policy_analysis
from .reporting import ResearchArtifactPaths, generate_research_artifacts
from .regional import add_pavlodar_regional_context, regional_summary

__all__ = [
    "AuditReport",
    "AblationScenario",
    "BenchmarkArtifactPaths",
    "DEFAULT_DATA_PATH",
    "DecisionReport",
    "ErrorAnalysisReport",
    "LocalExplanation",
    "LocalFactor",
    "PolicyAnalysisReport",
    "PROJECT_ROOT",
    "ResearchArtifactPaths",
    "TARGET_COLUMN",
    "ThresholdPolicy",
    "ablation_scenarios",
    "add_behavioral_features",
    "add_pavlodar_regional_context",
    "calibration_table",
    "load_uci_default_benchmark",
    "logistic_local_explanation",
    "make_model_frame",
    "normalize_uci_default_frame",
    "generate_research_artifacts",
    "regional_summary",
    "resolve_data_path",
    "run_ablation_study",
    "run_audit",
    "run_decision_analysis",
    "run_error_analysis",
    "run_policy_analysis",
    "run_uci_default_benchmark",
]
