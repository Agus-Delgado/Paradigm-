# Tableau — Diagnostic / exploratory layer (Paradigm v2)

**Status:** **assisted design and implementation** — CSV sources from the SQLite mart + workbook/story specification; `.twbx` is built in **Tableau Desktop** (binary not versioned by default).

**Role:** **exploration, segment comparison, and driver / cause analysis** (“why” and “where to dig”), not the one-screen executive summary. Complements Power BI per [`../powerbi/README.md`](../powerbi/README.md).

**Sources of truth:** [`docs/metrics.md`](../../docs/metrics.md), views in [`sql/views/`](../../sql/views/), mart at `data/processed/paradigm_mart.db` after [`scripts/build_sqlite_mart.py`](../../scripts/build_sqlite_mart.py), quality via [`scripts/run_data_quality.py`](../../scripts/run_data_quality.py).

**Out of scope for this workbook:** native ML model building inside Tableau; the **documented prioritization experiment** and training entrypoints live in [`ml/README.md`](../../ml/README.md). Also: occupancy proxy as a numeric KPI; cash collected as strict finance; **any metric not listed** in the dictionary.

**Trunk questions (T1–T6):** [`docs/analytical_questions.md`](../../docs/analytical_questions.md).

---

## 1. Analytic dashboard scope (vs Power BI executive)

| Dimension | Power BI (executive) | Tableau (this layer) |
|-----------|----------------------|----------------------|
| Main question | “What happened in the period and what number summarizes operations?” | “Which segments explain behavior and how do time, channel, and specialty combine?” |
| Grain | Monthly/daily for global trend; few cards | **Appointment grain** and simultaneous multiple cuts; dense tables |
| Time | One clear primary axis (appointment date for operations; billing separate) | **Several anchors** explicit in one workbook (appointment vs billing vs cancellation) |
| Typical visual | KPI cards, one trend, breakdown bars | Scatter, heatmap, stacked bars by cause, **parameter** thresholds and drill |
| Duplication | — | **Do not** repeat the “single executive page” (same 4–6 cards and story); Tableau answers **additional** questions below |

**Questions Tableau should answer (priority):**

1. **Operational root cause:** which **specialty × channel × weekday** (or month) combination concentrates no-shows or cancellations?
2. **Segment comparison:** how do specialties and channels rank on **rate** vs **volume** (two different reads)?
3. **Cancellation:** profile by **cancellation reason** (where present) and **early vs late** cancel (late = fewer than 24 hours before start)?
4. **Billing vs schedule:** where are **reconciliation** gaps (care–billing bridge) and do they cluster by cuts?
5. **Temporal:** daily or weekly trends **with** dimension filters **without** losing coherence (same dictionary logic).

**Leave in Power BI (do not rerun as main narrative in Tableau):** the same global KPI row and “one screen in 30–60 s” story. Tableau may **reference** those metrics for cross-check, not duplicate the executive dashboard.

---

## 2. Data sources

### 2.1 Recommendation (simplicity + mart consistency)

| CSV export (script output) | SQL source | Primary Tableau use |
|----------------------------|-------------|---------------------|
| `AppointmentBase.csv` | `vw_appointment_base` | **Main fact (appointment grain):** status, specialty, channel, role dates, `appointment_iso_week`, `appointment_day_of_week`, cancel reason |
| `BillingLine.csv` | `fact_billing_line` | Billed revenue with **`billing_date`**; join to appointment on `appointment_id` |
| `DimDate.csv` | `dim_date` | Calendar hierarchies and ISO week if joined on `appointment_date_key` / equivalent keys |
| `DimBillingStatus.csv` | `dim_billing_status` | Billing line status labels |
| `DailyKpis.csv` | `vw_daily_kpis` | **Global** daily series (rates defined in SQL); **no** specialty/channel — market-total helper only |
| `KpiBySpecialty.csv` | `vw_kpis_by_specialty` | **Monthly** by specialty (operations + `revenue_facturado_mes` with alignment note) |
| `KpiByProvider.csv` | `vw_kpis_by_provider` | **Monthly** by provider (same revenue caveat as specialty) |
| `RevenueBridge.csv` | `vw_revenue_bridge` | Reconciliation per appointment: buckets and amounts aggregated per appointment |

**Recommended Tableau model:** relational — `AppointmentBase` as hub; **LEFT** join `BillingLine` on `appointment_id` (1:N); `DimDate` on `appointment_date_key` / date as appropriate; optional `RevenueBridge` on `appointment_id` to avoid duplicating bucket logic.

**No separate mart schema** is required: same entities validated by the quality report.

### 2.2 Tableau CSV export

From repo root:

```text
python scripts/build_sqlite_mart.py
python scripts/export_tableau_source.py
```

Output: `bi/tableau/source_csv/`. Encoding **UTF-8 with BOM** (`utf-8-sig`) for Excel/Tableau on Windows.

**Dedicated Tableau export?** Yes in the sense of **folder + dedicated script** (`export_tableau_source.py`) including **`KpiByProvider`**, useful for provider analysis without recomputing from appointment grain. **No new metric** is introduced—only the SQL view already defined.

If a single ultra-flat table is needed later (all dimensions on one billing line row), add a SQL view `vw_billing_line_enriched` to the mart and extend the export—not required for the analytic MVP described here.

---

## 3. Suggested workbook (or story) structure

Convention: several **worksheets** + global filters (period, specialty, channel). Optional **Story** with three steps “volume → rate → cause.”

| Sheet / section | Goal | Suggested visual |
|-----------------|------|------------------|
| **A — Schedule heatmap** | Patterns by **weekday** and **specialty** (or channel) | Heatmap: `appointment_day_of_week` × `specialty_name`, color = no-show rate or % cancelled (minimum cell size by volume in tooltip) |
| **B — No-show and attendance** | Evolution and comparison | Lines (week/month) from **appointment grain** or `DailyKpis` for totals; side-by-side bars by specialty |
| **C — Cancellation and reasons** | Volume and rate; cause | Stacked bars or treemap by `cancellation_reason_description` (filter `CANCELLED`); summary table |
| **D — Channels** | Behavior by `booking_channel_name` | Sorted bars + scatter volume vs rate (same definitions as SQL samples) |
| **E — Late cancellation** | Threshold: fewer than 24 hours before start | Compute in Tableau (see §4); histogram or bars by hour/day bucket |
| **F — Billing and gap** | Separate P&L from schedule | View with **`billing_date`**; table or bars by billing month; **another** view with `RevenueBridge` by `reconciliation_bucket` |
| **G — Light “cohort”** | Only if data supports | **Not** classic retention cohorts (dictionary lacks rules). **MVP substitute:** matrix **booking month** × **appointment month** (schedule pipeline) using `booking_date` vs `appointment_date`, color = volume or no-show % |

**Heatmap:** supported with `appointment_day_of_week` + business dimension from `AppointmentBase`.

**Cohorts:** the model does not define patient cohort KPIs; booking vs appointment month matrix is **schedule pipeline** analysis, not “retention.” Label accordingly.

---

## 4. Calculations and logic (conceptual)

All formulas must **reconcile** with [`docs/metrics.md`](../../docs/metrics.md). Below: intent and dependencies; Tableau syntax may use LOD, `SUM`/`COUNT`, etc.

| Topic | Dictionary definition | Dependencies / anchor |
|-------|----------------------|------------------------|
| **No-show rate** | No-show / (attended + no-show) | Appointments with date in period; **appointment date** |
| **Cancellation rate (agenda in month)** | Cancelled / all appointments with date in period | **Appointment date** |
| **Cancellation by cancel date** | Different question: filter on `cancellation_date_key` / `cancellation_ts` | **Do not** mix in one visual with appointment-date cancel rate without subtitle |
| **Late cancellation rate** | Among cancelled, % with cancel fewer than 24 hours before `appointment_start` | Parse `cancellation_ts` and `appointment_start`; denominator = cancelled (MVP) |
| **Billed revenue** | Sum `line_amount` excluding VOID; period = **`billing_date`** | Independent of appointment month; do not compare monthly billing to monthly appointment volume **on one axis** without labeling |
| **Revenue in `KpiBySpecialty` / `KpiByProvider`** | Already mixes appointment month with billing month in join | Use with **warning** label (see [`sql/README.md`](../../sql/README.md)) |

**Make time relationships explicit in titles:** “Operations (appointment date)” vs “Billing (billing date)” vs “Cancellation recorded (cancel timestamp).”

---

## 5. Risks and limits

| Risk | Mitigation |
|------|------------|
| **Two cancellation definitions** (appointment date vs cancel moment) | Separate worksheets or “anchor mode” parameter; fixed subtitles |
| **Monthly revenue in pre-aggregated views** vs appointment month | Do not plot that revenue on the same chart as appointment volume **without** a note; prefer `BillingLine` for billing analysis |
| **`vw_daily_kpis` without dimensions** | Do not filter the chart as if it responds to specialty/channel |
| **Synthetic data** | Avoid causal inference; treat as **method** demo |
| **Occupancy proxy** | Do not publish as numeric KPI (no slots in mart) |
| **Cash collected** | Do not show as real cash collection (see dictionary) |
| **Provider evaluation** | Operational productivity only; not “clinical quality” |

**Avoid in Tableau at this phase:** a dashboard that repeats the **same KPI hierarchy** as the Power BI executive; geographic maps without a geographic dimension; any metric invented outside the dictionary.

**Extra transforms:** for **hour-of-day** axis, derive hour from `appointment_start` in Tableau or a future SQL view; justify by analysis volume (not in minimal MVP).

---

## 6. MVP deliverable limits

- Tableau workbook **built manually or semi-manually** from `bi/tableau/source_csv/` following this spec.
- Optional numeric cross-check vs [`scripts/run_data_quality.py`](../../scripts/run_data_quality.py) and mart totals.
- No Tableau Server required; Desktop + image export for documentation.

---

## 7. Evidence for root README (when `.twbx` exists)

- Capture **one heatmap** and **one cause/reason view** (non-sensitive if applicable).
- One line: “Deep analysis in Tableau; executive view in Power BI” with links to `bi/tableau/README.md` and `bi/powerbi/README.md`.
- Optional: relative path under [`../../assets/`](../../assets/) if thumbnails are stored.

---

## Cross references

- Metrics dictionary: [`docs/metrics.md`](../../docs/metrics.md)
- SQL view notes: [`sql/README.md`](../../sql/README.md)
- Executive Power BI: [`../powerbi/README.md`](../powerbi/README.md)
- Aligned SQL samples: [`sql/samples/`](../../sql/samples/)
