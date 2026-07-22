# Python — Paradigm core

## Role in the project

| Package | Layer | Role |
|---------|-------|------|
| `paradigm.io` | Observe | Paths / mart location |
| `paradigm.quality` | Observe | Checks + Markdown report |
| `paradigm.ml` | Predict | No-show sobre mart portfolio |
| `paradigm.synthetic_v2` | Observe/Predict (lab) | Generador con señal controlable (no reemplaza `data/synthetic/`) |
| `paradigm.ml_v2` | Predict (lab) | No-show + uplift sobre synthetic_v2 |
| `paradigm.prescriptive` | Decide | Motor headless de política / ranking |
| `paradigm.monitoring` | Learn | Segmentación + drift |

Mapa completo: [`docs/FINAL_ARCHITECTURE.md`](../docs/FINAL_ARCHITECTURE.md).

There is no heavy **raw → processed** transform in the portfolio path: the **analytic source** for BI is SQLite built from `data/synthetic/`. Quality validates that mart before visualization tools connect.

## Recommended flow (reproducible)

From the **repository root**:

```bash
python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py
python scripts/run_data_quality.py
python scripts/export_powerbi_source.py
python scripts/validate_executive_kpis.py
python scripts/train_no_show.py
```

For Power BI: import CSV from `bi/powerbi/source_csv/` (see [`bi/powerbi/README.md`](../bi/powerbi/README.md)). Optional ML experiment outputs in `ml/experiments/` — see [`../ml/README.md`](../ml/README.md).

1. **Synthetic** — CSV in `data/synthetic/`.
2. **Mart** — `data/processed/paradigm_mart.db` (DDL + load + SQL views).
3. **Quality** — Python checks and **`reports/quality_report.md`**.

### Running quality

```bash
python scripts/run_data_quality.py
```

**PYTHONPATH:** the script adds `python/src` to the path; local development does not require `pip install -e .`.

**Exit code:** `0` if no checks with severity **fail**; `1` if any fail. **Warn** (e.g. attended-without-billing in synthetic data) **does not** change exit code.

### What it validates

Summary (detail in code: `paradigm/quality/checks.py`):

| Topic | Behavior |
|-------|----------|
| Integrity | `PRAGMA integrity_check`, `PRAGMA foreign_key_check` |
| Uniqueness | No duplicate `appointment_id`, `billing_line_id` |
| Nulls | Required columns on facts |
| Dates | `booking_date` ≤ `appointment_date` |
| Status | Cancelled ↔ `cancellation_ts`; reason only if cancelled |
| Amounts | `line_amount` ≥ 0; currency `ARS` |
| References | Billing lines reference existing appointments |
| `dim_date` | Every `appointment_date` exists on calendar |
| Care vs billing | **WARN** if attended rows lack billing lines (expected in synthetic demo for reconciliation) |

### Artifact

| File | Description |
|------|-------------|
| `reports/quality_report.md` | Results table + legend; suitable for portfolio or CI. |

### Limits of this phase

- Does not validate CSV **before** load (operational truth is SQLite after `build_sqlite_mart.py`).
- Does not replace exhaustive unit tests or clinical business rules.
- A **WARN** does not block the pipeline; review detail before publishing dashboards.

## Other

- `notebooks/` — optional EDA.

## See also

- [`sql/README.md`](../sql/README.md) — DDL, views, sample SQL.
- [`docs/data_dictionary.md`](../docs/data_dictionary.md) — data contract.
