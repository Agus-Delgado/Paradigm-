# SQL — Paradigm v2 (local SQLite)

## Why SQLite

- **Portability:** a single file (`data/processed/paradigm_mart.db`) cloneable without a server.
- **Portfolio:** demonstrates DDL, views, and reproducible queries on any machine with Python.
- **Scope:** local analytical layer aligned to the dimensional model; Power BI / Tableau can connect to the `.db` or consume CSV exports from views.

**Limitation:** not a concurrent production engine; sufficient for MVP and demos.

## Building and loading the database

1. Generate CSVs under [`data/synthetic/`](../data/synthetic/README.md):

   ```bash
   python scripts/generate_paradigm_v2_synthetic.py
   ```

2. Run the build (DDL + load + views):

   ```bash
   python scripts/build_sqlite_mart.py
   ```

3. (Recommended) Validate mart quality and write the report:

   ```bash
   python scripts/run_data_quality.py
   ```

   Output: `reports/quality_report.md` — see [`python/README.md`](../python/README.md).

Step 2 produces **`data/processed/paradigm_mart.db`** (overwrites if it already existed).

Requirements: Python 3.10+ with `pandas` (see [`requirements.txt`](../requirements.txt)).

## Schema (DDL)

Defined in [`ddl/01_create_tables.sql`](ddl/01_create_tables.sql):

- Dimensions: `dim_date`, `dim_specialty`, `dim_coverage`, `dim_appointment_status`, `dim_booking_channel`, `dim_billing_status`, `dim_cancellation_reason`, `dim_patient`, `dim_provider`.
- Facts: `fact_appointment`, `fact_billing_line`.

Foreign keys enabled (`PRAGMA foreign_keys = ON` in the build script).

## Analytic views

| View | Purpose |
|------|---------|
| `vw_appointment_base` | Appointments enriched with dimensions and `appointment_date_key` / `booking_date_key` / `cancellation_date_key`. |
| `vw_daily_kpis` | KPIs by **appointment date**: totals, attended, cancelled, no-shows, rates (definitions in [`docs/metrics.md`](../docs/metrics.md)). |
| `vw_kpis_by_specialty` | **Monthly** aggregation by operational specialty; includes `revenue_facturado_mes` with **billing month** (`billing_date`) aligned to the same `year_month` as the appointment month (see note below). |
| `vw_kpis_by_provider` | Same by provider. |
| `vw_revenue_bridge` | Per **appointment**: amounts by billing status type and `reconciliation_bucket` (e.g. `ATTENDED_NO_BILLING`). |

### Revenue note on specialty / provider views

`revenue_facturado_mes` uses **`strftime('%Y-%m', billing_date)`** with specialty/provider from the appointment. The join with operational KPIs (based on **`appointment_date`**) uses the same **`year_month` labeling**: in practice revenue and appointments align when billing and appointment fall in the same calendar month; if a line bills in a different month than the visit, effects split across **billing** months (expected for billed revenue).

## Sample queries

In [`samples/`](samples/):

| File | Topic |
|------|--------|
| `01_no_show_by_specialty.sql` | No-show by specialty |
| `02_cancellation_by_channel.sql` | Cancellation by channel |
| `03_attended_by_month.sql` | Attended appointments by month |
| `04_billing_by_month.sql` | Billing by month (`billing_date`) |
| `05_reconciliation_attendance_vs_billing.sql` | Reconciliation via `vw_revenue_bridge` |

Run with the SQLite CLI if installed:

```bash
sqlite3 data/processed/paradigm_mart.db < sql/samples/01_no_show_by_specialty.sql
```

Or use any SQL client pointed at the `.db` file.

## Limitations of this phase

- No stored procedures or jobs: **load** is the Python script.
- **Cash collected** not modeled as real finance (line statuses only; `PAID` is a proxy per dictionary).
- **Occupancy proxy** not materialized in a view yet (capacity rule per provider/day in SQL or BI pending).
- Views **do not** replace the metrics dictionary: always validate definitions in [`docs/metrics.md`](../docs/metrics.md).
