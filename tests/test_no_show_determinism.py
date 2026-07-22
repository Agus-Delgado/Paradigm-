"""Regression tests and audit helpers for no-show reproducibility."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from paradigm.io.paths import DB_PATH  # noqa: E402
from paradigm.ml.dataset import load_eligible_appointments  # noqa: E402
from paradigm.ml.evaluate import classification_metrics, top_fraction_capture  # noqa: E402
from paradigm.ml.features import (  # noqa: E402
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    add_booking_calendar_features,
    add_historical_features,
    build_model_frame,
)
from paradigm.ml.train import (  # noqa: E402
    _build_logistic,
    _build_rf,
    _predict_deterministically,
    _rf_importances,
    _temporal_split_by_appointment_date,
)
from sklearn.metrics import accuracy_score  # noqa: E402


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Stable hash including column order, dtypes, index, and cell values."""
    header = json.dumps(
        {
            "columns": [str(column) for column in df.columns],
            "dtypes": [str(dtype) for dtype in df.dtypes],
            "index_name": str(df.index.name),
        },
        sort_keys=True,
    ).encode("utf-8")
    values = pd.util.hash_pandas_object(df, index=True).to_numpy(dtype="uint64").tobytes()
    return _sha256_bytes(header + values)


def _hash_series(series: pd.Series) -> str:
    return _hash_dataframe(series.to_frame(name=str(series.name)))


def _hash_array(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    descriptor = f"{value.dtype}|{value.shape}".encode("ascii")
    return _sha256_bytes(descriptor + value.tobytes())


def _model_metrics(y_true: pd.Series, proba: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    metrics = classification_metrics(y_true, proba)
    metrics["accuracy"] = float(accuracy_score(y_true, pred))
    metrics["top_decile"] = top_fraction_capture(y_true, proba, fraction=0.1)
    return metrics


def capture_training_diagnostics(db_path: Path = DB_PATH) -> dict[str, Any]:
    """Run the deterministic training core without writing production artifacts."""
    raw = load_eligible_appointments(db_path)
    featured = add_historical_features(add_booking_calendar_features(raw))
    train_df, test_df, cutoff = _temporal_split_by_appointment_date(featured, test_ratio=0.2)
    X_train, y_train = build_model_frame(train_df)
    X_test, y_test = build_model_frame(test_df)

    logistic = _build_logistic()
    random_forest = _build_rf()
    logistic.fit(X_train, y_train)
    random_forest.fit(X_train, y_train)

    logistic_proba, logistic_pred = _predict_deterministically(logistic, X_test)
    rf_proba, rf_pred = _predict_deterministically(random_forest, X_test)

    return {
        "versions": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "rows": {
            "dataset": len(featured),
            "train": len(train_df),
            "test": len(test_df),
        },
        "cutoff": cutoff,
        "feature_columns": list(X_train.columns),
        "transformer_features": {
            "numeric": list(NUMERIC_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
            "output": list(logistic.named_steps["prep"].get_feature_names_out()),
        },
        "row_order": featured["appointment_id"].astype(str).tolist(),
        "train_indices": train_df.index.astype(int).tolist(),
        "test_indices": test_df.index.astype(int).tolist(),
        "y_test_values": y_test.astype(int).tolist(),
        "hashes": {
            "dataset": _hash_dataframe(featured),
            "X_train": _hash_dataframe(X_train),
            "X_test": _hash_dataframe(X_test),
            "y_train": _hash_series(y_train),
            "y_test": _hash_series(y_test),
            "logistic_proba": _hash_array(logistic_proba),
            "logistic_pred": _hash_array(logistic_pred),
            "rf_proba": _hash_array(rf_proba),
            "rf_pred": _hash_array(rf_pred),
        },
        "probabilities": {
            "logistic": logistic_proba.tolist(),
            "random_forest": rf_proba.tolist(),
        },
        "predictions": {
            "logistic": logistic_pred.astype(int).tolist(),
            "random_forest": rf_pred.astype(int).tolist(),
        },
        "metrics": {
            "baseline_logistic": _model_metrics(y_test, logistic_proba, logistic_pred),
            "random_forest": {
                **_model_metrics(y_test, rf_proba, rf_pred),
                "feature_importances_top": _rf_importances(random_forest),
            },
        },
        "_models": {
            "baseline_logistic": logistic,
            "random_forest": random_forest,
        },
    }


def _public_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


class TestNoShowDeterminism(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not DB_PATH.is_file():
            raise unittest.SkipTest(f"Mart missing: {DB_PATH}")

    def test_two_equivalent_trainings_are_identical(self) -> None:
        first = capture_training_diagnostics()
        second = capture_training_diagnostics()

        self.assertEqual(first["row_order"], second["row_order"])
        self.assertEqual(first["feature_columns"], second["feature_columns"])
        self.assertEqual(first["transformer_features"], second["transformer_features"])
        self.assertEqual(first["train_indices"], second["train_indices"])
        self.assertEqual(first["test_indices"], second["test_indices"])
        self.assertEqual(first["y_test_values"], second["y_test_values"])
        self.assertEqual(first["hashes"], second["hashes"])
        self.assertEqual(first["probabilities"], second["probabilities"])
        self.assertEqual(first["predictions"], second["predictions"])
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual(first["_models"]["random_forest"].named_steps["clf"].n_jobs, -1)
        self.assertEqual(second["_models"]["random_forest"].named_steps["clf"].n_jobs, -1)

    def test_serialized_models_are_identical_in_temporary_directories(self) -> None:
        first = capture_training_diagnostics()
        second = capture_training_diagnostics()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hashes: dict[str, list[str]] = {
                "baseline_logistic": [],
                "random_forest": [],
            }
            for run_number, result in enumerate((first, second), start=1):
                for model_name, model in result["_models"].items():
                    path = root / f"run_{run_number}_{model_name}.joblib"
                    joblib.dump(model, path)
                    hashes[model_name].append(_sha256_bytes(path.read_bytes()))

        self.assertEqual(hashes["baseline_logistic"][0], hashes["baseline_logistic"][1])
        self.assertEqual(hashes["random_forest"][0], hashes["random_forest"][1])


if __name__ == "__main__":
    unittest.main()
