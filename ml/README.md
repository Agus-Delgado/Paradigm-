# Machine Learning — Paradigm v2

## Honest framing

This repository contains a **reproducible prioritization experiment** over **synthetic** outpatient-style data. It is **not** a production **no-show prediction** product, clinical decision system, or deployable screening model.

- **Observed metrics:** on the current synthetic generator, **ROC-AUC is near or below 0.5** (see `ml/experiments/metrics.json`). That outcome is treated as a **documented limitation** of synthetic signal strength and sample characteristics—not something to hide or cast as a “broken” implementation.
- **What the portfolio demonstrates:** **methodology**—explicit **target** definition, **leakage** controls, **temporal** train/test split, a **feature** catalog aligned to the mart, **evaluation** logic (ranking-style reads such as top-decile capture), and an **operational framing** (“who might you contact first?”), not leaderboard accuracy.
- **Real deployment would require:** real historical data with governance, **monitoring** and drift checks, **calibration** and threshold processes fit to the organization, **privacy and security** review, and **clinical/operational validation**—none of which this repo claims to deliver.

## Positioning: methodology-first prioritization experiment

This module adds a **ranking-oriented experiment** on top of the same mart as BI: it produces scores for **prioritization / ordering** (e.g. reminder lists) at the **documented booking-time decision point**. It does **not** replace descriptive analysis or diagnostic BI; it is **not** a production service. It uses the **same mart** as Tableau and Power BI and must be read with [`docs/metrics.md`](../docs/metrics.md) and synthetic-data **limitations**.

**Status:** **implemented (MVP)** — appointment-grain labels aligned to the metrics dictionary and SQLite mart; outputs are **evidence of process**, not a validated predictor.

**Sources of truth:** [`docs/metrics.md`](../docs/metrics.md), mart [`data/processed/paradigm_mart.db`](../data/processed/) via [`scripts/build_sqlite_mart.py`](../scripts/build_sqlite_mart.py).

### Operational decision connection

The score supports decisions such as:

- **Prioritized reminders** or pre-visit contact when predicted risk is high (concrete policies stay outside the repo).
- **Review of higher-risk segments** in aggregate (e.g. to focus analysis or pilot outreach in a real setting).
- **Preventive monitoring** combined with BI cuts: the model suggests *where to look*, not automated actions.

Basic **explainability** comes from model **feature importances** and an honest read of `metrics.json`; these are not causal claims.

---

## 1. Problem

Estimate **no-show probability** at **booking time**, to prioritize contacts or reminder campaigns (operations layer; fine policy stays with the business).

---

## 2. Target variable

- **Definition:** `target_no_show = 1` if the appointment ends **NO_SHOW**, `0` if **ATTENDED**.
- **Row universe:** only appointments with status **ATTENDED** or **NO_SHOW** (same universe as the no-show rate denominator in [`docs/metrics.md`](../docs/metrics.md): **cancelled** appointments are not part of this label).
- **What this model is not:** cancellation prediction (different label and time window).

---

## 3. Decision point and leakage

| Moment | Meaning |
|--------|---------|
| **Decision point (scoring)** | Immediately **after booking**: everything observable at **`booking_ts` / `booking_date`** and the chosen **appointment calendar** (scheduled date/time). |
| **Included (no leakage)** | Channel, specialty, coverage, provider, patient (age band, sex), **lead time** (appointment − booking), day/hour of appointment and approximate booking hour, **prior history** for patient and provider on **strictly earlier** appointments. |
| **Excluded (leakage)** | Final status beyond what the model universe allows, **cancellation** and reasons, **any billing** or charge lines, aggregates that include the current appointment in “past,” or information after the appointment day. |

Historical features use only appointments with **appointment date strictly before** the current row (order by `appointment_date`, `appointment_start`, `appointment_id` within patient and provider).

---

## 4. Dataset and features

**Construction:** read from SQLite (`fact_appointment` + `dim_appointment_status` + `dim_patient`) in [`paradigm/ml/dataset.py`](../python/src/paradigm/ml/dataset.py); feature engineering in [`paradigm/ml/features.py`](../python/src/paradigm/ml/features.py).

| Type | Features (MVP) |
|------|----------------|
| **At booking + appointment calendar** | `lead_time_days`, `appointment_hour`, `appointment_dow`, `appointment_month`, `booking_hour`; categoricals `provider_id`, `specialty_id`, `booking_channel_id`, `coverage_id`, `age_band`, `sex`. |
| **Historical (no leakage)** | Prior counts and rates for **patient** and **provider:** `patient_prior_appt_count`, `patient_prior_no_show_count`, `patient_prior_no_show_rate`, analogous `provider_prior_*`. |
| **Not used** | Appointment status, cancellation, billing, using sensitive patient IDs as a clinical “score” (tabular mart features only). |

---

## 5. Temporal split and evaluation

- **Split:** by **appointment date** `appointment_date` (not random row sampling). Train = dates **≤ cutoff**; test = dates **after** cutoff. Cutoff leaves ~`1 - test_ratio` of **distinct dates** in train (`test_ratio` default `0.2` in [`train.py`](../python/src/paradigm/ml/train.py)).
- **Ranking metrics:** ROC-AUC, average precision (PR-AUC), Brier score.
- **Operational read:** **capture rate** of actual no-shows in the **top 10%** of predicted risk on test (`top_decile` in `metrics.json`): share of no-shows falling in that decile when ranking by descending score.

---

## 6. Models

| Model | Role |
|--------|------|
| **Logistic regression** (`lbfgs`, `class_weight=balanced`) | Interpretable linear baseline. |
| **Random Forest** (`n_estimators=120`, `max_depth=10`, `class_weight=balanced`) | Primary model with **feature importances** exported to `metrics.json`. |

No aggressive hyperparameter search; goal is a defensible, reproducible portfolio artifact.

---

## 7. Interpretation

- Random Forest **importances** reflect column weight after one-hot encoding; they are **not** causal effects.
- Poor metrics or test AUC **below 0.5** are **possible** with **synthetic** data and small samples: the deliverable is **methodology** (decision point, leakage rules, temporal split, business-oriented metrics), not leaderboard accuracy.

### Lightweight explainability checklist

When presenting the model (portfolio or interview), use the tabular checklist in [`docs/analytical_questions.md`](../docs/analytical_questions.md) (section 4): **signal**, **universe**, **decision point**, **technical evidence** (`metrics.json`), **importances** (not causality), **use risks**, **suggested action type** (prioritization, not in-repo automation).

---

## 8. Synthetic-data limitations

- No-show patterns may be **weak or unrealistic**; avoid clinical or commercial extrapolation.
- Modest sample size → high variance in AUC/PR on the test slice.
- **Honesty:** if `metrics.json` shows poor performance, treat it as **risk documentation**, not broken implementation.

---

## 9. How to run

From the **repository root** (same environment as the rest of the project; install dependencies with `pip install -r requirements.txt`):

```bash
python scripts/build_sqlite_mart.py
python scripts/train_no_show.py
```

**Outputs:**

| Path | Content |
|------|---------|
| `ml/experiments/no_show_logistic.joblib` | Trained baseline pipeline |
| `ml/experiments/no_show_random_forest.joblib` | Trained Random Forest pipeline |
| `ml/experiments/metrics.json` | Train/test dates, metrics, importances, top-decile capture |

**Optional Python load (exploratory inference):**

```python
import joblib
from pathlib import Path

pipe = joblib.load(Path("ml/experiments/no_show_random_forest.joblib"))
# X must match training structure (see paradigm.ml.features)
# proba = pipe.predict_proba(X)[:, 1]
```

---

## 10. Code layout

| Path | Role |
|------|------|
| [`python/src/paradigm/ml/dataset.py`](../python/src/paradigm/ml/dataset.py) | Loads eligible appointments and target |
| [`python/src/paradigm/ml/features.py`](../python/src/paradigm/ml/features.py) | History + calendar; column lists |
| [`python/src/paradigm/ml/evaluate.py`](../python/src/paradigm/ml/evaluate.py) | Metrics and top-fraction capture |
| [`python/src/paradigm/ml/train.py`](../python/src/paradigm/ml/train.py) | Temporal split, training, artifacts |
| [`scripts/train_no_show.py`](../scripts/train_no_show.py) | Reproducible entrypoint |

Notebooks are optional; flow is script + importable package.

---

## 11. Possible next steps (not implemented)

Illustrative evolution only—not scope commitments: explicit **cancellation** modeling, behavior **clustering**, or other techniques aligned to the same mart and business definitions. The MVP centers on **no-show** as the documented **prioritization experiment** case study.
