"""Pipeline uplift Two-Model sobre policy_intervention (synthetic_v2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from paradigm.ml_v2.dataset import load_eligible_v2
from paradigm.ml_v2.features import (
    FORBIDDEN_FEATURE_COLUMNS,
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
    assert_no_leakage,
    build_model_frame,
)
from paradigm.ml_v2.train import (
    _build_logistic,
    _build_rf,
    _json_safe,
    _predict_deterministically,
    temporal_split_by_appointment_date,
)
from paradigm.ml_v2.uplift_metrics import (
    policy_value_curves,
    qini_metrics,
    segment_recovery,
    spearman_corr,
    true_benefit_from_ite_probability,
    uplift_by_decile,
    uplift_score_from_probs,
)

TREATMENT_COLUMN = "extra_reminder"
OUTCOME_COLUMN = "target_no_show"

# Selección por Qini en hold-out (no conectado a política de costos).
UPLIFT_SELECTED_MODEL = "random_forest"


def _require_intervention_columns(df: pd.DataFrame) -> None:
    needed = [TREATMENT_COLUMN, OUTCOME_COLUMN]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas de intervención/outcome: {missing}")


def _split_arms(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = df[TREATMENT_COLUMN].astype(int)
    treated = df[t == 1]
    control = df[t == 0]
    if len(treated) < 20 or len(control) < 20:
        raise ValueError(
            f"Brazos insuficientes para Two-Model: treated={len(treated)} control={len(control)}"
        )
    return treated, control


def _fit_arm_models(
    *,
    seed: int,
    train_df: pd.DataFrame,
) -> dict[str, dict[str, Pipeline]]:
    """Entrena modelos T=0 y T=1 para logistic y random_forest."""
    treated, control = _split_arms(train_df)
    X_t1, y_t1 = build_model_frame(treated)
    X_t0, y_t0 = build_model_frame(control)
    assert_no_leakage(X_t1.columns)
    assert_no_leakage(X_t0.columns)
    # Tratamiento y truth nunca como features
    assert TREATMENT_COLUMN not in X_t1.columns
    assert TREATMENT_COLUMN not in X_t0.columns

    models: dict[str, dict[str, Pipeline]] = {
        "logistic_regression": {
            "control": _build_logistic(seed),
            "treated": _build_logistic(seed + 1),
        },
        "random_forest": {
            "control": _build_rf(seed),
            "treated": _build_rf(seed + 1),
        },
    }
    models["logistic_regression"]["control"].fit(X_t0, y_t0)
    models["logistic_regression"]["treated"].fit(X_t1, y_t1)
    models["random_forest"]["control"].fit(X_t0, y_t0)
    models["random_forest"]["treated"].fit(X_t1, y_t1)
    return models


def _score_two_model(
    models: dict[str, Pipeline],
    X: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p0, _ = _predict_deterministically(models["control"], X)
    p1, _ = _predict_deterministically(models["treated"], X)
    uplift = uplift_score_from_probs(p0, p1)
    return p0, p1, uplift


def _evaluate_family(
    *,
    name: str,
    models: dict[str, Pipeline],
    test_df: pd.DataFrame,
    X_test: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    p0, p1, uplift = _score_two_model(models, X_test)

    if "true_ite_probability" in test_df.columns:
        benefits = true_benefit_from_ite_probability(
            test_df["true_ite_probability"].to_numpy(dtype=float)
        )
    else:
        # Fallback observado (menos ideal): no usar truth
        benefits = uplift.copy() * 0.0

    qini = qini_metrics(uplift, benefits)
    deciles = uplift_by_decile(uplift, benefits)
    policy = policy_value_curves(uplift, benefits)
    segments = segment_recovery(test_df, uplift, top_fraction=0.2)
    spearman = spearman_corr(uplift, benefits)

    metrics: dict[str, Any] = {
        "model_name": name,
        "approach": "two_model",
        "mean_predicted_uplift": float(np.mean(uplift)),
        "mean_true_benefit": float(np.mean(benefits)),
        "spearman_vs_true_benefit": spearman,
        "qini": qini,
        "uplift_by_decile": deciles,
        "policy_value": policy,
        "segment_recovery_top20": segments,
        "n_test": int(len(test_df)),
        "treatment_rate_test": float(test_df[TREATMENT_COLUMN].astype(int).mean()),
    }

    preds = pd.DataFrame(
        {
            "appointment_id": test_df["appointment_id"].to_numpy(),
            "appointment_date": pd.to_datetime(test_df["appointment_date"]).dt.strftime("%Y-%m-%d"),
            "extra_reminder": test_df[TREATMENT_COLUMN].astype(int).to_numpy(),
            "y_true": test_df[OUTCOME_COLUMN].astype(int).to_numpy(),
            f"p0_{name}": p0,
            f"p1_{name}": p1,
            f"uplift_{name}": uplift,
        }
    )
    if "true_ite_probability" in test_df.columns:
        preds["true_ite_probability"] = test_df["true_ite_probability"].astype(float).to_numpy()
        preds["true_benefit"] = benefits
    if "true_p0" in test_df.columns:
        preds["true_p0"] = test_df["true_p0"].astype(float).to_numpy()
        preds["true_p1"] = test_df["true_p1"].astype(float).to_numpy()

    return metrics, preds


def select_uplift_model(metrics_by_model: dict[str, dict[str, Any]]) -> str:
    """Elige el modelo con mayor Qini coefficient; desempate: RF por defecto."""
    best_name = UPLIFT_SELECTED_MODEL
    best_q = float("-inf")
    for name, block in metrics_by_model.items():
        q = float((block.get("qini") or {}).get("qini_coefficient", float("-inf")))
        if q > best_q + 1e-12:
            best_q = q
            best_name = name
        elif abs(q - best_q) <= 1e-12 and name == UPLIFT_SELECTED_MODEL:
            best_name = name
    return best_name


def run_uplift_training_v2(
    *,
    dataset_id: str,
    out_dir: Path,
    data_root: Path | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Two-Model uplift: modelos separados en T=0 / T=1, score = p̂0 − p̂1.

    Excluye truth, potential outcomes, treatment y costo del feature set.
    No conecta política de costos / umbrales.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_eligible_v2(dataset_id, data_root=data_root)
    _require_intervention_columns(raw)
    train_df, test_df, cutoff_str = temporal_split_by_appointment_date(raw, test_ratio=test_ratio)

    X_test, _ = build_model_frame(test_df)
    assert_no_leakage(X_test.columns)
    leak_overlap = sorted(set(X_test.columns) & set(FORBIDDEN_FEATURE_COLUMNS))
    if leak_overlap:
        raise ValueError(f"Leakage en features: {leak_overlap}")

    assert train_df["appointment_date"].max() <= pd.Timestamp(cutoff_str)
    assert test_df["appointment_date"].min() > pd.Timestamp(cutoff_str)

    family_models = _fit_arm_models(seed=seed, train_df=train_df)

    metrics_lr, preds_lr = _evaluate_family(
        name="logistic_regression",
        models=family_models["logistic_regression"],
        test_df=test_df,
        X_test=X_test,
    )
    metrics_rf, preds_rf = _evaluate_family(
        name="random_forest",
        models=family_models["random_forest"],
        test_df=test_df,
        X_test=X_test,
    )

    metrics_by_model = {
        "logistic_regression": metrics_lr,
        "random_forest": metrics_rf,
    }
    selected = select_uplift_model(metrics_by_model)

    # Merge predictions
    predictions = preds_lr.merge(
        preds_rf[
            [
                "appointment_id",
                "p0_random_forest",
                "p1_random_forest",
                "uplift_random_forest",
            ]
        ],
        on="appointment_id",
        how="inner",
    )
    predictions["uplift_selected"] = predictions[f"uplift_{selected}"]
    predictions["selected_model"] = selected

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        family_models["logistic_regression"]["control"],
        models_dir / "uplift_logistic_control.joblib",
    )
    joblib.dump(
        family_models["logistic_regression"]["treated"],
        models_dir / "uplift_logistic_treated.joblib",
    )
    joblib.dump(
        family_models["random_forest"]["control"],
        models_dir / "uplift_rf_control.joblib",
    )
    joblib.dump(
        family_models["random_forest"]["treated"],
        models_dir / "uplift_rf_treated.joblib",
    )

    pred_path = out_dir / "predictions" / "test_uplift_predictions.csv"
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(pred_path, index=False)

    treated_n = int((train_df[TREATMENT_COLUMN].astype(int) == 1).sum())
    control_n = int((train_df[TREATMENT_COLUMN].astype(int) == 0).sum())

    summary: dict[str, Any] = {
        "dataset_id": dataset_id,
        "pipeline": "uplift_v2_two_model",
        "approach": "two_model",
        "treatment_column": TREATMENT_COLUMN,
        "uplift_definition": "p0_hat - p1_hat  # expected no-show reduction",
        "temporal_cutoff_appointment_date": cutoff_str,
        "test_ratio_target": test_ratio,
        "seed": seed,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_train_treated": treated_n,
        "n_train_control": control_n,
        "train_date_min": str(train_df["appointment_date"].min().date()),
        "train_date_max": str(train_df["appointment_date"].max().date()),
        "test_date_min": str(test_df["appointment_date"].min().date()),
        "test_date_max": str(test_df["appointment_date"].max().date()),
        "features_categorical": list(PREDECISIONAL_CATEGORICAL),
        "features_numeric": list(PREDECISIONAL_NUMERIC),
        "excluded_from_features": sorted(
            set(FORBIDDEN_FEATURE_COLUMNS)
            | {
                TREATMENT_COLUMN,
                "intervention_cost",
                "true_y0",
                "true_y1",
                "true_ite",
                "true_p0",
                "true_p1",
                "true_ite_probability",
            }
        ),
        "metrics": metrics_by_model,
        "selected_model": selected,
        "selection_rule": "max_qini_coefficient_on_holdout",
        "predictions_path": str(pred_path),
        "notes": (
            "No conectado a política de costos/umbrales. "
            "Truth solo para evaluación (Qini / policy value / segmentos)."
        ),
    }

    summary_path = out_dir / "uplift_training_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(summary), f, indent=2, ensure_ascii=False)
    summary["uplift_training_summary_path"] = str(summary_path)
    return summary
