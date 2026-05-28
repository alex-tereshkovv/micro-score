"""Training and evaluation pipeline for MicroScore."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .paths import DEFAULT_DATA_PATH, PROJECT_ROOT, resolve_data_path

RANDOM_STATE = 42


@dataclass
class ModelResult:
    name: str
    estimator: Pipeline
    test_metrics: dict[str, float]
    cv_metrics: dict[str, tuple[float, float]]
    feature_importance: pd.DataFrame
    confusion_matrix: np.ndarray


def load_dataset(path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(resolve_data_path(path))


def _one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", _one_hot_encoder()),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, make_column_selector(dtype_include=np.number)),
            ("cat", categorical_pipeline, make_column_selector(dtype_exclude=np.number)),
        ]
    )


def build_logistic_regression(random_state: int = RANDOM_STATE) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=random_state,
                ),
            ),
        ]
    )


def build_random_forest(random_state: int = RANDOM_STATE) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            (
                "model",
                RandomForestClassifier(
                    class_weight="balanced",
                    min_samples_leaf=10,
                    n_estimators=300,
                    n_jobs=-1,
                    random_state=random_state,
                ),
            ),
        ]
    )


def build_models(random_state: int = RANDOM_STATE) -> dict[str, Callable[[], Pipeline]]:
    return {
        "Logistic Regression": lambda: build_logistic_regression(random_state),
        "Random Forest": lambda: build_random_forest(random_state),
    }


def _test_metrics(
    y_true: pd.Series,
    y_pred: np.ndarray,
    y_probability: np.ndarray,
) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "roc_auc": roc_auc_score(y_true, y_probability),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def _cv_metrics(
    estimator: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    random_state: int = RANDOM_STATE,
) -> dict[str, tuple[float, float]]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
    scores = cross_validate(
        estimator,
        X,
        y,
        cv=cv,
        scoring={
            "accuracy": "accuracy",
            "roc_auc": "roc_auc",
            "precision": "precision",
            "recall": "recall",
            "f1": "f1",
        },
        n_jobs=None,
    )
    return {
        metric.removeprefix("test_"): (float(values.mean()), float(values.std()))
        for metric, values in scores.items()
        if metric.startswith("test_")
    }


def _clean_feature_names(feature_names: np.ndarray) -> list[str]:
    return [
        name.replace("num__", "").replace("cat__", "")
        for name in feature_names
    ]


def feature_importance(estimator: Pipeline) -> pd.DataFrame:
    preprocessor = estimator.named_steps["preprocess"]
    model = estimator.named_steps["model"]
    names = _clean_feature_names(preprocessor.get_feature_names_out())

    if hasattr(model, "coef_"):
        values = model.coef_[0]
        column_name = "coefficient"
    elif hasattr(model, "feature_importances_"):
        values = model.feature_importances_
        column_name = "importance"
    else:
        return pd.DataFrame(columns=["feature", "value", "abs_value"])

    importance = pd.DataFrame(
        {
            "feature": names,
            column_name: values,
            "abs_value": np.abs(values),
        }
    )
    return importance.sort_values("abs_value", ascending=False).reset_index(drop=True)


def evaluate_model(
    name: str,
    estimator: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    *,
    random_state: int = RANDOM_STATE,
) -> ModelResult:
    cv_summary = _cv_metrics(estimator, X_train, y_train, random_state=random_state)
    fitted = clone(estimator)
    fitted.fit(X_train, y_train)

    y_pred = fitted.predict(X_test)
    y_probability = fitted.predict_proba(X_test)[:, 1]

    return ModelResult(
        name=name,
        estimator=fitted,
        test_metrics=_test_metrics(y_test, y_pred, y_probability),
        cv_metrics=cv_summary,
        feature_importance=feature_importance(fitted),
        confusion_matrix=confusion_matrix(y_test, y_pred),
    )


def run_experiment(
    data_path: str | Path = DEFAULT_DATA_PATH,
    *,
    target: str = TARGET_COLUMN,
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> list[ModelResult]:
    frame = load_dataset(data_path)
    return run_experiment_on_frame(
        frame,
        target=target,
        drop_columns=drop_columns,
        random_state=random_state,
        test_size=test_size,
    )


def run_experiment_on_frame(
    frame: pd.DataFrame,
    *,
    target: str = TARGET_COLUMN,
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> list[ModelResult]:
    X, y = make_model_frame(frame, target=target, drop_columns=drop_columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    results: list[ModelResult] = []
    for name, model_factory in build_models(random_state).items():
        results.append(
            evaluate_model(
                name,
                model_factory(),
                X_train,
                X_test,
                y_train,
                y_test,
                random_state=random_state,
            )
        )
    return results


def results_table(results: list[ModelResult]) -> pd.DataFrame:
    rows = []
    for result in results:
        row = {"model": result.name}
        row.update({f"test_{key}": value for key, value in result.test_metrics.items()})
        row.update(
            {
                f"cv_{metric}_mean": mean
                for metric, (mean, _std) in result.cv_metrics.items()
            }
        )
        row.update(
            {
                f"cv_{metric}_std": std
                for metric, (_mean, std) in result.cv_metrics.items()
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)
