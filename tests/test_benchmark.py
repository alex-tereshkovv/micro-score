from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.benchmark import normalize_uci_default_frame, run_uci_default_benchmark
from microscore.modeling import build_logistic_regression


def _sample_uci_frame(rows: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(37)
    target = np.array([0, 1] * (rows // 2))
    delayed = target * 2 + rng.integers(-1, 2, size=rows)
    return pd.DataFrame(
        {
            "ID": np.arange(1, rows + 1),
            "LIMIT_BAL": rng.integers(20_000, 500_000, size=rows),
            "SEX": np.where(np.arange(rows) % 2 == 0, 1, 2),
            "EDUCATION": rng.choice([1, 2, 3, 4], size=rows),
            "MARRIAGE": rng.choice([1, 2, 3], size=rows),
            "AGE": rng.integers(21, 70, size=rows),
            "PAY_0": delayed,
            "PAY_2": delayed + rng.integers(-1, 2, size=rows),
            "PAY_3": delayed + rng.integers(-1, 2, size=rows),
            "PAY_4": delayed + rng.integers(-1, 2, size=rows),
            "PAY_5": delayed + rng.integers(-1, 2, size=rows),
            "PAY_6": delayed + rng.integers(-1, 2, size=rows),
            "BILL_AMT1": rng.normal(80_000, 20_000, size=rows).clip(0),
            "BILL_AMT2": rng.normal(76_000, 20_000, size=rows).clip(0),
            "BILL_AMT3": rng.normal(72_000, 20_000, size=rows).clip(0),
            "BILL_AMT4": rng.normal(68_000, 20_000, size=rows).clip(0),
            "BILL_AMT5": rng.normal(64_000, 20_000, size=rows).clip(0),
            "BILL_AMT6": rng.normal(60_000, 20_000, size=rows).clip(0),
            "PAY_AMT1": rng.normal(8_000, 2_000, size=rows).clip(0),
            "PAY_AMT2": rng.normal(7_500, 2_000, size=rows).clip(0),
            "PAY_AMT3": rng.normal(7_000, 2_000, size=rows).clip(0),
            "PAY_AMT4": rng.normal(6_500, 2_000, size=rows).clip(0),
            "PAY_AMT5": rng.normal(6_000, 2_000, size=rows).clip(0),
            "PAY_AMT6": rng.normal(5_500, 2_000, size=rows).clip(0),
            "default payment next month": target,
        }
    )


class BenchmarkTests(unittest.TestCase):
    def test_normalize_uci_default_frame_maps_target_and_categories(self) -> None:
        normalized = normalize_uci_default_frame(_sample_uci_frame())

        self.assertIn("credit_risk", normalized.columns)
        self.assertIn("customer_id", normalized.columns)
        self.assertIn("limit_balance", normalized.columns)
        self.assertIn("payment_status_sep", normalized.columns)
        self.assertEqual(set(normalized["credit_risk"].unique()), {0, 1})
        self.assertTrue(set(normalized["sex"].unique()).issubset({"male", "female"}))

    def test_run_uci_default_benchmark_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            factories = {
                "Logistic Regression": lambda: build_logistic_regression(37),
            }
            artifacts = run_uci_default_benchmark(
                frame=_sample_uci_frame(),
                output_dir=tempdir,
                model_factories=factories,
                random_state=37,
                n_bins=5,
            )

            for path in artifacts.files:
                self.assertTrue(path.exists(), path)

            manifest = json.loads(artifacts.manifest_json.read_text(encoding="utf-8"))
            self.assertEqual(manifest["benchmark"], "UCI Default of Credit Card Clients")
            self.assertEqual(manifest["rows"], 100)

            metrics = pd.read_csv(artifacts.model_metrics_csv)
            calibration = pd.read_csv(artifacts.calibration_csv)
            features = pd.read_csv(artifacts.top_features_csv)
            segment_errors = pd.read_csv(artifacts.segment_error_csv)

            self.assertIn("test_roc_auc", metrics.columns)
            self.assertIn("calibration_error", calibration.columns)
            self.assertIn("feature", features.columns)
            self.assertIn("segment_feature", segment_errors.columns)
            self.assertIn(
                "UCI Credit Default Benchmark Artifacts",
                artifacts.summary_markdown.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
