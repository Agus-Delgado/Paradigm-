# Power BI — Executive dashboard (v2 design)

**Status:** **assisted implementation** — exported CSV + DAX + canvas instructions; the `.pbix` file is built in **Power BI Desktop** (binary not versioned by default).

**Role:** monitoring for **leadership / operations** — “what happened in the period” and “what to look at first,” without replacing deep analysis (reserved for Tableau: [`bi/tableau/README.md`](../tableau/README.md)).

**Sources of truth:** [`docs/metrics.md`](../../docs/metrics.md), views in [`sql/views/`](../../sql/views/), data in `data/processed/paradigm_mart.db` after [`scripts/build_sqlite_mart.py`](../../scripts/build_sqlite_mart.py) and quality via [`scripts/run_data_quality.py`](../../scripts/run_data_quality.py).

**Trunk questions (T1–T6) and traceability:** [`docs/analytical_questions.md`](../../docs/analytical_questions.md).

---

## 1. Exact executive dashboard scope (MVP)

| Included | Excluded (out of this canvas / later phase) |
|----------|-----------------------------------------------|
| Operational KPIs with **appointment date** as main axis | **Occupancy proxy** (no dedicated SQL view; avoid misleading cards) |
| **No-show** and **cancellation** rates aligned to dictionary | **Late cancellation rate** (fine time logic; better in Tableau or a future view) |
| **Attended appointment** volume | **Cash collected** as real finance (no payment date in MVP) |
| **Billed revenue** with **`billing_date`** anchor (separate from operations) | Any KPI not listed in [`docs/metrics.md`](../../docs/metrics.md) |
| **Attendance–billing gap** indicator (count / soft alert) | **ML / scoring** on this canvas (see [`ml/README.md`](../../ml/README.md)) |

**One PBIX file, one main page (“Executive”)** in MVP; optional second page (“Reference”) only if long legends are needed — prioritize **one screen** readable in 30–60 s.

---

## 2. Canvas structure — pages and sections

### Recommended single page: **Executive**

| Section | Goal | Expected read |
|---------|------|-----------------|
| **A — Filter bar** | Narrow period and business cuts | Same interpretation as metrics dictionary |
| **B — KPI cards** | Key numbers for selected period | Maximum 4–6 cards |
| **C — Time trend** | Volume or rate evolution (schedule) | One line or area; weekly or monthly grain |
| **D — Breakdown** | Compare **specialty** or **provider** | Horizontal bars, sorted |
| **E — Operational alert** | Billing gaps on attended visits | Short table or card |

**Per block:** B answers “how much”; C “how it trends” (**schedule only**); D “where”; E “what billing should review.”

---

## 3. KPIs, visuals, and SQL sources

### 3.1 Power BI modeling principles

- **Operations (schedule):** anchor **`appointment_date`** (and derivatives on `vw_appointment_base`).
- **Billing:** anchor **`billing_date`** on `fact_billing_line` — **do not** mix with `appointment_date` in one visual unless the design states it (see §5).

**Recommended primary table for filters and operational measures:** **`vw_appointment_base`** (appointment grain; includes `specialty_name`, `provider_label`, `channel_code`, `status_code`, role dates).

**Billing fact:** **`fact_billing_line`** related to `vw_appointment_base` on `appointment_id` (1:N from appointment to lines).

**Pre-aggregated views:** use to **reduce DAX** on monthly charts, not as the only source when slicers do not apply (see §3.3).

### 3.2 KPI → visual → source → time anchor

| KPI (dictionary) | Suggested visual | Preferred source | Time anchor |
|------------------|------------------|-------------------|-------------|
| Total appointments (operational denominator) | Card | `vw_appointment_base` — row count | **Appointment date** |
| Attended appointments | Card | `vw_appointment_base` — filter `status_code = "ATTENDED"` | **Appointment date** |
| No-show rate | Card (%) | Measure on `vw_appointment_base`: no-show / (attended + no-show) | **Appointment date** |
| Cancellation rate (on agenda in period) | Card (%) | Same base: cancelled / all appointments with date in period | **Appointment date** |
| Billed revenue | Card (amount) | `fact_billing_line` — sum `line_amount` where status ≠ VOID | **`billing_date`** |
| Reconciliation gaps (attended without billing count) | Card or short table | `vw_revenue_bridge` — filter `reconciliation_bucket = "ATTENDED_NO_BILLING"` | Appointment / bucket (operational); amounts from lines if present |
| Volume trend | Line or area | **`vw_daily_kpis`** only if axis is time **without** needing specialty filters on the same chart **or** measure on `vw_appointment_base` by `appointment_date` | **Appointment date** |
| Breakdown by specialty | Horizontal bars | **`vw_kpis_by_specialty`** or measures on `vw_appointment_base` by `specialty_name` | Operations: **appointment month** (`year_month` in view); revenue in that view follows billing alignment per [`sql/README.md`](../../sql/README.md) |
| Breakdown by provider | Horizontal bars | **`vw_kpis_by_provider`** or measures on `vw_appointment_base` by `provider_label` | Same as specialty |

### 3.3 Current view limitations (important)

| View | Executive use | Limitation |
|------|----------------|------------|
| `vw_daily_kpis` | Daily trend of rates and counts | **No** specialty, provider, or channel. If the user filters by specialty in the bar, this chart **must not** keep showing the global series without clarification: **prefer** trend from `vw_appointment_base` with the same filters, or hide trend when dimension filters apply. |
| `vw_kpis_by_specialty` / `vw_kpis_by_provider` | Monthly bars | Pre-aggregated by `year_month` + dimension. **Revenue** in the view follows **billing month** joined to the same `year_month` as appointment month (see `sql/README.md`); **misalignment** can occur between appointment month and billing month. Label the revenue visual. |
| `vw_revenue_bridge` | Gap alert | Appointment grain; good for **counts** by `reconciliation_bucket`. |
| Occupancy proxy | — | **No SQL view**; do not show as numeric KPI in MVP or show text “not available in mart.” |

**No new SQL views** are required for executive MVP if you import `vw_appointment_base` + `fact_billing_line` and accept the notes above. A future optional view `vw_daily_kpis_by_specialty` would simplify filtered trends — **out of scope for this design iteration**.

---

## 4. Conceptual measures (business logic, no DAX)

Power BI should define measures with these **names and meanings** (DAX implementation later):

| Conceptual measure | Dependencies / logic | Notes |
|--------------------|----------------------|-------|
| `Citas Total` | Rows in `vw_appointment_base` in filter context | Anchor: `appointment_date` |
| `Citas Atendidas` | `status_code = "ATTENDED"` | Same |
| `Citas Canceladas` | `status_code = "CANCELLED"` | Same |
| `Citas No Show` | `status_code = "NO_SHOW"` | Same |
| `No Show Rate` | `[Citas No Show] / ([Citas Atendidas] + [Citas No Show])` | Blank if denominator zero |
| `Tasa Cancelacion` | `[Citas Canceladas] / [Citas Total]` | Appointments with date in period |
| `Ingreso Facturado` | Sum `line_amount` on `fact_billing_line` with billing status ≠ VOID | Filter by **`billing_date`** in period (billing date table or measure with `USERELATIONSHIP` if using two date roles) |
| `Citas Atendidas Sin Facturacion` | `COUNTROWS` on `vw_revenue_bridge` where bucket = `ATTENDED_NO_BILLING` | Operational read only |

**Date relationships:** use **`dim_date`** with active relationship to `vw_appointment_base[appointment_date]` and **inactive** relationship or duplicate “Billing” calendar to `fact_billing_line[billing_date]` to avoid mixing anchors on one axis by mistake.

---

## 5. Filters and navigation

### Global filters (slicers)

| Filter | Suggested field | Source |
|--------|-----------------|--------|
| Period (schedule) | `appointment_date` or `dim_date` | Appointment date range |
| Specialty | `specialty_name` | `vw_appointment_base` |
| Provider | `provider_label` | `vw_appointment_base` |
| Booking channel | `channel_code` or `booking_channel_name` | `vw_appointment_base` |
| Appointment status | `status_code` | **Optional** on executive (filtering “attended only” changes rates); use with tooltip help |

**Billing period:** if showing billed revenue, use a **separate slicer** on `billing_date` or a clear “Schedule vs Billing” toggle to avoid confusion.

**Navigation:** MVP without bookmark buttons; single canvas.

---

## 6. Risks and methodology notes

| Topic | Action on canvas |
|-------|-------------------|
| Schedule vs billing | Label cards: “Schedule (appointment date)” vs “Billing (issue date)” |
| `revenue_facturado_mes` on monthly views | Short tooltip: possible appointment vs billing month mismatch |
| Data quality | After `run_data_quality.py`, **WARN** on attended-without-line is **expected**; gap card reinforces |
| Provider rankings | Footer note: metrics are **operational**, not clinical quality ([`docs/problem.md`](../../docs/problem.md)) |
| Local SQLite | Keep connector updated; use relative paths if the repo moves |

---

## 7. Implemented data source (MVP)

**Decision:** export **CSV** from the same SQLite mart as SQL views for maximum portability without relying on SQLite connectors on every machine.

| Mart source | CSV in `source_csv/` | Use in Power BI |
|-------------|----------------------|-----------------|
| `vw_appointment_base` | `AppointmentBase.csv` | Operational fact, filters, trend, breakdown |
| `fact_billing_line` + `dim_billing_status` | `BillingLine.csv`, `DimBillingStatus.csv` | Billed revenue (exclude VOID via relationship + measure) |
| `dim_date` | `DimDate.csv` | Schedule date axis (optional) |
| `vw_revenue_bridge` | `RevenueBridge.csv` | Gap measure (`ATTENDED_NO_BILLING`) |
| `vw_daily_kpis`, `vw_kpis_by_specialty` | `DailyKpis.csv`, `KpiBySpecialty.csv` | Optional / reference (MVP canvas prefers measures on `AppointmentBase`) |

**Generation:**

```bash
python scripts/build_sqlite_mart.py
python scripts/export_powerbi_source.py
```

Output: [`source_csv/`](source_csv/).

---

## 8. What the repo contains vs manual Power BI work

| Artifact | Location |
|----------|----------|
| Ready-to-import CSV | `bi/powerbi/source_csv/*.csv` |
| DAX measures | [`dax/executive_measures.dax`](dax/executive_measures.dax) |
| Model and canvas steps | [`BUILD_INSTRUCTIONS.md`](BUILD_INSTRUCTIONS.md) |
| Numeric validation | `python scripts/validate_executive_kpis.py` |

**Manual step:** create `.pbix` in Power BI Desktop importing CSV, relationships, measures, and visuals per `BUILD_INSTRUCTIONS.md`.

---

## 9. KPIs covered by measures (MVP)

Aligned to [`docs/metrics.md`](../../docs/metrics.md):

| Measure | Type |
|---------|------|
| `Citas Total` | Operational (appointment date) |
| `Citas Atendidas` / `Citas Canceladas` / `Citas No Show` | Operational |
| `No Show Rate` | Operational |
| `Tasa Cancelacion` | Operational |
| `Ingreso Facturado` | Billing (`billing_date` on slicer; see BUILD_INSTRUCTIONS interactions) |
| `Citas Atendidas Sin Facturacion` | Reconciliation (consistent with `vw_revenue_bridge`) |

**Out of scope:** occupancy proxy, late cancel, real cash collected, ML.

---

## 10. Validation against mart and quality report

Run:

```bash
python scripts/validate_executive_kpis.py
```

**Current reference (full synthetic mart, no date filters):** total appointments **520**, attended **368**, no-show rate **0.1300**, cancellation rate **0.1865**, total billed revenue **6,904,253.48** ARS, gap count **31** (matches quality WARN and `vw_revenue_bridge`).

**Known inconsistencies (do not expand scope without decision):**

- If **schedule** slicers filter the **billed revenue** card, totals may differ from global SQL — use **edit interactions** or a dedicated `billing_date` slicer (§4 of `BUILD_INSTRUCTIONS.md`).
- Imported `DailyKpis` is not mandatory for MVP; trend can be built from `AppointmentBase` to respect specialty filters.

---

## 11. Limitations of this phase

- No `.pbix` in the repository (optional locally; may be gitignored by size).
- **Direct** `.db` connection not required if regenerable CSVs are used.
- Tableau and ML: out of scope here.

---

## 12. Evidence for the root README

When the `.pbix` is built:

1. Capture the **Executive** page → save as [`assets/dashboards/powerbi_executive.png`](../../assets/dashboards/powerbi_executive.png) (canonical name; replace the committed file when you refresh the design).
2. In the root README, one line: *Executive dashboard built in Power BI Desktop; CSV source + measures in `bi/powerbi/`.*

**Do not** require Tableau or ML screenshots here yet.
