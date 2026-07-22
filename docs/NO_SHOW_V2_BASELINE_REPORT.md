# Baseline no-show v2 — comparación de escenarios

**Fecha:** 2026-07-21
**Pipeline:** `paradigm.ml_v2` + `scripts/train_no_show_v2.py` (paralelo; no modifica mart ni `paradigm.ml` v1)
**Seed:** 42 · **Split:** temporal por `appointment_date` (test_ratio=0.2)
**Modelo seleccionado:** `random_forest` (misma política que v1)

## Runs

| Escenario | dataset_id | run_id |
|-----------|------------|--------|
| weak | `signal_weak_seed42` | `20260721_230255_no_show_v2_signal_weak_seed42` |
| moderate | `signal_moderate_seed42` | `20260721_230255_no_show_v2_signal_moderate_seed42` |
| strong | `signal_strong_seed42` | `20260721_230256_no_show_v2_signal_strong_seed42` |

Artefactos: `ml/experiments/runs/<run_id>/` (`metrics.json`, `models/`, `predictions/`, `report.md`).

## Features usadas (solo predecisionales)

**Categóricas:** `provider_id`, `specialty_id`, `booking_channel_id`, `coverage_id`, `age_band`, `sex`

**Numéricas:** `lead_time_days`, `appointment_hour`, `appointment_dow`, `appointment_month`, `booking_hour`, `reminder_sent`, `is_repeat_patient`, `patient_prior_*`, `provider_prior_*`

## Features excluidas (leakage / truth)

- Truth: `true_logit`, `true_no_show_probability`
- Latentes: `patient_propensity_u`, `provider_effect_v`
- Post-outcome: `appointment_status_id`, `status_code`, `cancellation_ts`, `cancellation_reason_id`, billing
- Meta no usada como feature: `appointment_id`, `patient_id`, timestamps (solo split/join)

## Métricas hold-out — Random Forest (selected)

| Escenario | ROC-AUC | PR-AUC | Brier | Log loss | Precision | Recall | F1 | Top-decile capture | AUC(`true_p`) ref. |
|-----------|---------|--------|-------|----------|-----------|--------|----|--------------------|--------------------|
| weak | 0.506 | 0.131 | 0.147 | 0.474 | 0.250 | 0.088 | 0.130 | 0.118 | 0.553 |
| moderate | 0.646 | 0.254 | 0.174 | 0.534 | 0.231 | 0.214 | 0.222 | 0.167 | 0.716 |
| strong | 0.698 | 0.248 | 0.137 | 0.439 | 0.286 | 0.452 | 0.350 | 0.290 | 0.784 |

## Métricas hold-out — Logistic (baseline)

| Escenario | ROC-AUC | PR-AUC | Brier | Log loss | Precision | Recall | F1 | Top-decile capture |
|-----------|---------|--------|-------|----------|-----------|--------|----|--------------------|
| weak | 0.568 | 0.181 | 0.167 | 0.519 | 0.154 | 0.059 | 0.085 | 0.059 |
| moderate | 0.622 | 0.212 | 0.199 | 0.585 | 0.209 | 0.429 | 0.281 | 0.190 |
| strong | 0.711 | 0.268 | 0.142 | 0.438 | 0.214 | 0.387 | 0.276 | 0.258 |

## Lectura

1. **Señal ordenada en el modelo seleccionado (RF):** AUC 0.51 → 0.65 → 0.70 (weak < moderate < strong).
2. **`true_p` como techo de referencia** (no es un modelo): el RF queda por debajo del AUC generador en los tres casos; el gap es esperable (muestreo, split temporal, forma del modelo, ruido \(\varepsilon\)).
3. En **weak**, RF ≈ azar (0.51) mientras logistic alcanza 0.57 — señal insuficiente / inestable en hold-out.
4. En **strong**, logistic (0.711) supera ligeramente a RF (0.698); la selección sigue siendo RF por paridad con v1, no por máximo AUC.
5. Top-decile capture mejora con la señal (≈0.12 → 0.17 → 0.29 en RF).

## Hiperparámetros (iguales a v1)

- Logistic: `lbfgs`, `class_weight=balanced`, `max_iter=2000`, `random_state=seed`
- RF: `n_estimators=120`, `max_depth=10`, `min_samples_leaf=5`, `class_weight=balanced`, `n_jobs=-1`, `random_state=seed`

## Limitaciones

- Hold-out temporal; el AUC(`true_p`) del test puede diferir del AUC global del dataset.
- Precision/Recall/F1 usan umbral 0.5 (no calibrado operativamente).
- Pipeline v1 (mart SQLite) no se usó ni se modificó en estos runs.
