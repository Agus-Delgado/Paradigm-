"""Análisis de error y calibración para no-show v2 (sin cambiar el entrenamiento)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from paradigm.ml_v2.metrics import classification_metrics_v2

CHANNEL_NAMES = {1: "WEB", 2: "PHONE", 3: "RECEPTION"}
SPECIALTY_NAMES = {
    1: "Clinica medica",
    2: "Cardiologia",
    3: "Dermatologia",
    4: "Pediatria",
    5: "Ginecologia",
    6: "Traumatologia",
}

MODEL_PROBA_COLS = {
    "baseline_logistic": "proba_baseline_logistic",
    "random_forest": "proba_random_forest",
}


def _clip_proba(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)


def calibration_slope_intercept(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
) -> dict[str, float | None]:
    """
    Regresión logística: logit(P(Y=1)) ≈ a + b * logit(p_hat).
    Calibración perfecta ⇒ slope≈1, intercept≈0.
    """
    y = np.asarray(y_true).astype(int)
    p = _clip_proba(y_score)
    if len(np.unique(y)) < 2:
        return {"slope": None, "intercept": None, "n": float(len(y))}
    x = np.log(p / (1.0 - p)).reshape(-1, 1)
    clf = LogisticRegression(solver="lbfgs", max_iter=2000)
    clf.fit(x, y)
    return {
        "slope": float(clf.coef_.ravel()[0]),
        "intercept": float(clf.intercept_.ravel()[0]),
        "n": float(len(y)),
    }


def calibration_curve_points(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    *,
    n_bins: int = 10,
) -> dict[str, Any]:
    y = np.asarray(y_true).astype(int)
    p = np.asarray(y_score, dtype=float)
    if len(np.unique(y)) < 2 or len(y) < n_bins:
        return {"fraction_positives": [], "mean_predicted": [], "n_bins": n_bins}
    frac, mean_pred = calibration_curve(y, p, n_bins=n_bins, strategy="quantile")
    return {
        "fraction_positives": [float(x) for x in frac],
        "mean_predicted": [float(x) for x in mean_pred],
        "n_bins": int(n_bins),
        "strategy": "quantile",
    }


def risk_decile_metrics(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    *,
    n_deciles: int = 10,
) -> list[dict[str, Any]]:
    y = np.asarray(y_true).astype(int)
    p = np.asarray(y_score, dtype=float)
    order = np.argsort(p)
    y_s, p_s = y[order], p[order]
    n = len(y)
    rows: list[dict[str, Any]] = []
    for d in range(n_deciles):
        lo = int(np.floor(d * n / n_deciles))
        hi = int(np.floor((d + 1) * n / n_deciles))
        if hi <= lo:
            continue
        ys, ps = y_s[lo:hi], p_s[lo:hi]
        rows.append(
            {
                "decile": d + 1,
                "n": int(hi - lo),
                "mean_predicted": float(ps.mean()),
                "observed_rate": float(ys.mean()),
                "positives": int(ys.sum()),
                "calibration_gap": float(ys.mean() - ps.mean()),
            }
        )
    return rows


def confusion_counts(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    *,
    threshold: float = 0.5,
) -> dict[str, Any]:
    y = np.asarray(y_true).astype(int)
    pred = (np.asarray(y_score, dtype=float) >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "threshold": float(threshold)}


def _lead_bin(lead: float) -> str:
    if lead <= 3:
        return "0-3"
    if lead <= 7:
        return "4-7"
    if lead <= 14:
        return "8-14"
    if lead <= 30:
        return "15-30"
    return "31+"


def _hour_bin(hour: int) -> str:
    if hour < 12:
        return "8-11"
    if hour < 15:
        return "12-14"
    return "15-17"


def segment_error_table(
    frame: pd.DataFrame,
    *,
    proba_col: str,
    segment_col: str,
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, g in frame.groupby(segment_col, dropna=False):
        y = g["y_true"].to_numpy().astype(int)
        p = g[proba_col].to_numpy(dtype=float)
        pred = (p >= threshold).astype(int)
        n = len(g)
        pos = int(y.sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        auc = float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None
        rows.append(
            {
                "segment": str(key),
                "n": n,
                "positives": pos,
                "observed_rate": float(y.mean()) if n else None,
                "mean_predicted": float(p.mean()) if n else None,
                "brier": float(brier_score_loss(y, p)) if n and len(np.unique(y)) > 1 else None,
                "roc_auc": auc,
                "fp": fp,
                "fn": fn,
                "fp_rate": float(fp / max(n - pos, 1)),
                "fn_rate": float(fn / max(pos, 1)),
            }
        )
    rows.sort(key=lambda r: (-(r["n"] or 0), str(r["segment"])))
    return rows


def build_analysis_frame(
    predictions: pd.DataFrame,
    appointments: pd.DataFrame,
) -> pd.DataFrame:
    """Une predicciones hold-out con covariables predecisionales del fact."""
    cols = [
        "appointment_id",
        "lead_time_days",
        "booking_channel_id",
        "appointment_hour",
        "specialty_id",
        "is_repeat_patient",
    ]
    missing = [c for c in cols if c not in appointments.columns]
    if missing:
        raise KeyError(f"Faltan columnas en fact_appointment: {missing}")
    meta = appointments[cols].copy()
    meta["channel"] = meta["booking_channel_id"].map(CHANNEL_NAMES).fillna(
        meta["booking_channel_id"].astype(str)
    )
    meta["specialty"] = meta["specialty_id"].map(SPECIALTY_NAMES).fillna(
        meta["specialty_id"].astype(str)
    )
    meta["lead_bin"] = meta["lead_time_days"].map(_lead_bin)
    meta["hour_bin"] = meta["appointment_hour"].astype(int).map(_hour_bin)
    meta["recurrence"] = np.where(meta["is_repeat_patient"].astype(int) == 1, "repeat", "first")
    out = predictions.merge(meta, on="appointment_id", how="left", validate="one_to_one")
    return out


def analyze_model(
    frame: pd.DataFrame,
    *,
    model_name: str,
    proba_col: str,
    threshold: float = 0.5,
) -> dict[str, Any]:
    y = frame["y_true"]
    p = frame[proba_col]
    metrics = classification_metrics_v2(y, p, threshold=threshold)
    return {
        "model": model_name,
        "proba_col": proba_col,
        "holdout_metrics": metrics,
        "calibration": {
            **calibration_slope_intercept(y, p),
            "curve": calibration_curve_points(y, p, n_bins=10),
            "brier": metrics.get("brier"),
        },
        "risk_deciles": risk_decile_metrics(y, p, n_deciles=10),
        "confusion": confusion_counts(y, p, threshold=threshold),
        "segments": {
            "lead_bin": segment_error_table(frame, proba_col=proba_col, segment_col="lead_bin"),
            "channel": segment_error_table(frame, proba_col=proba_col, segment_col="channel"),
            "hour_bin": segment_error_table(frame, proba_col=proba_col, segment_col="hour_bin"),
            "specialty": segment_error_table(frame, proba_col=proba_col, segment_col="specialty"),
            "recurrence": segment_error_table(frame, proba_col=proba_col, segment_col="recurrence"),
        },
    }


def compare_models(analyses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compara LR vs RF en ranking, calibración y errores."""
    lr = analyses["baseline_logistic"]
    rf = analyses["random_forest"]
    lr_c = lr["calibration"]
    rf_c = rf["calibration"]

    def _abs_dev(slope: float | None, intercept: float | None) -> float | None:
        if slope is None or intercept is None:
            return None
        return abs(slope - 1.0) + abs(intercept)

    lr_dev = _abs_dev(lr_c.get("slope"), lr_c.get("intercept"))
    rf_dev = _abs_dev(rf_c.get("slope"), rf_c.get("intercept"))
    better_calibrated = None
    if lr_dev is not None and rf_dev is not None:
        better_calibrated = "baseline_logistic" if lr_dev <= rf_dev else "random_forest"

    lr_auc = (lr.get("holdout_metrics") or {}).get("roc_auc")
    rf_auc = (rf.get("holdout_metrics") or {}).get("roc_auc")
    better_ranking = None
    if isinstance(lr_auc, (int, float)) and isinstance(rf_auc, (int, float)):
        better_ranking = "random_forest" if rf_auc >= lr_auc else "baseline_logistic"

    return {
        "better_calibrated": better_calibrated,
        "better_ranking_auc": better_ranking,
        "logistic_calibration_dev": lr_dev,
        "rf_calibration_dev": rf_dev,
        "logistic_roc_auc": lr_auc,
        "rf_roc_auc": rf_auc,
        "logistic_brier": lr_c.get("brier"),
        "rf_brier": rf_c.get("brier"),
        "logistic_fp_fn": lr.get("confusion"),
        "rf_fp_fn": rf.get("confusion"),
    }


def analyze_predictions(
    predictions: pd.DataFrame,
    appointments: pd.DataFrame,
    *,
    threshold: float = 0.5,
) -> dict[str, Any]:
    frame = build_analysis_frame(predictions, appointments)
    models = {
        name: analyze_model(frame, model_name=name, proba_col=col, threshold=threshold)
        for name, col in MODEL_PROBA_COLS.items()
    }
    return {
        "n_test": int(len(frame)),
        "positive_rate": float(frame["y_true"].mean()),
        "models": models,
        "comparison": compare_models(models),
    }


def load_run_predictions(run_dir: Path) -> pd.DataFrame:
    path = Path(run_dir) / "predictions" / "test_predictions.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def save_calibration_plot(
    analysis_model: dict[str, Any],
    *,
    title: str,
    out_path: Path,
) -> Path | None:
    """Guarda curva de calibración (matplotlib). Devuelve None si no hay puntos."""
    curve = (analysis_model.get("calibration") or {}).get("curve") or {}
    mean_pred = curve.get("mean_predicted") or []
    frac = curve.get("fraction_positives") or []
    if not mean_pred or not frac:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], "k--", label="Perfect")
    ax.plot(mean_pred, frac, "o-", label="Model")
    slope = (analysis_model.get("calibration") or {}).get("slope")
    intercept = (analysis_model.get("calibration") or {}).get("intercept")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(
        0.05,
        0.95,
        f"slope={slope:.3f}\nintercept={intercept:.3f}" if slope is not None else "",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def multi_seed_stability(
    dataset_id: str,
    seeds: list[int],
    *,
    data_root: Path | None = None,
    test_ratio: float = 0.2,
) -> dict[str, Any]:
    """Reentrena con distintas seeds (hiperparámetros fijos) y resume AUC/Brier."""
    from paradigm.ml_v2.train import run_training_v2
    import tempfile

    per_model: dict[str, dict[str, list[float]]] = {
        "baseline_logistic": {"roc_auc": [], "brier": [], "pr_auc": []},
        "random_forest": {"roc_auc": [], "brier": [], "pr_auc": []},
    }
    details: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for seed in seeds:
            summary = run_training_v2(
                dataset_id=dataset_id,
                out_dir=root / f"seed_{seed}",
                data_root=data_root,
                test_ratio=test_ratio,
                seed=seed,
            )
            row: dict[str, Any] = {"seed": seed}
            for model in ("baseline_logistic", "random_forest"):
                m = summary["metrics"][model]
                for key in ("roc_auc", "brier", "pr_auc"):
                    val = m.get(key)
                    if isinstance(val, (int, float)):
                        per_model[model][key].append(float(val))
                        row[f"{model}_{key}"] = float(val)
            details.append(row)

    def _stats(vals: list[float]) -> dict[str, float]:
        arr = np.asarray(vals, dtype=float)
        return {
            "mean": float(arr.mean()) if len(arr) else float("nan"),
            "std": float(arr.std(ddof=0)) if len(arr) else float("nan"),
            "min": float(arr.min()) if len(arr) else float("nan"),
            "max": float(arr.max()) if len(arr) else float("nan"),
        }

    return {
        "dataset_id": dataset_id,
        "seeds": list(seeds),
        "n_seeds": len(seeds),
        "models": {
            model: {metric: _stats(vals) for metric, vals in metrics.items()}
            for model, metrics in per_model.items()
        },
        "details": details,
    }
