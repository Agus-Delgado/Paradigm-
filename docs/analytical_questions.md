# Paradigm — Trunk analytical questions and traceability

This document is the **conceptual backbone** of the analytic framework: **trunk questions** (T1–T6), the **matrix** to KPIs, SQL, BI consumption and illustrative actions, **decision use cases**, a **lightweight explainability checklist** for the predictive layer, and the boundary between documented scope and future technical work.

Repository data are **synthetic**; numeric answers are **illustrative**. Value lies in **definitions, traceability, and defensible narrative**.

**Related docs:** KPI definitions in [`metrics.md`](metrics.md); dimensional layout and flow in [`architecture.md`](architecture.md); business framing in [`problem.md`](problem.md); no-show modeling in [`ml/README.md`](../ml/README.md).

---

## 1. Trunk diagnostic questions (T1–T6)

Each trunk id (**T1–T6**) is used throughout this document and in [`problem.md`](problem.md).

### T1 — Trends over time

| | |
|--|--|
| **Business question** | How do **no-show**, **cancellation**, **attended appointments**, and aggregate operational volume evolve over time? |
| **Metrics / methods** | No-show rate, cancellation rate, attended count, daily/monthly trends — see [`metrics.md`](metrics.md) §2–3, §5; operational volume from appointment facts. |
| **BI / SQL direction** | `vw_daily_kpis`; `sql/samples/03_attended_by_month.sql`; exports `DailyKpis.csv` for trend. |
| **Why it matters** | Detect sustained deterioration before optimizing isolated slots; aligns leadership on whether the period is stable or drifting. |

### T2 — Where friction concentrates

| | |
|--|--|
| **Business question** | **Where** does operational friction concentrate by **specialty**, **booking channel**, and **time** (day, slot)? |
| **Metrics / methods** | No-show and cancellation rates by segment; productivity cuts — [`metrics.md`](metrics.md) §2–3, §10–12. |
| **BI / SQL direction** | `vw_kpis_by_specialty`; `sql/samples/01_no_show_by_specialty.sql`; `sql/samples/02_cancellation_by_channel.sql`; `KpiBySpecialty.csv`, `AppointmentBase.csv`. |
| **Why it matters** | Targets remediation (channels, capacity perception, communication) where the signal repeats, not random one-off spikes. |

### T3 — Late cancellations

| | |
|--|--|
| **Business question** | Where do **late cancellations** (fewer than 24 hours before start) concentrate, and in which channel–service combinations? |
| **Metrics / methods** | Late cancellation rate — [`metrics.md`](metrics.md) §4; cancellation context §3. |
| **BI / SQL direction** | `vw_appointment_base` (timestamps for the under-24-hours rule); `sql/samples/02_cancellation_by_channel.sql` where relevant; Tableau per [`bi/tableau/README.md`](../bi/tableau/README.md). Executive MVP may omit late cancel — see [`bi/powerbi/README.md`](../bi/powerbi/README.md). |
| **Why it matters** | Late cancels block refill; operational levers (reminders, windows) differ from generic cancel rates. |

### T4 — Billed revenue vs attended activity

| | |
|--|--|
| **Business question** | How does **billed revenue** evolve and how does it relate to **attended** appointments in the analyzed window? |
| **Metrics / methods** | Billed revenue by `billing_date`; revenue per attended appointment — [`metrics.md`](metrics.md) §6, §8. |
| **BI / SQL direction** | `vw_kpis_by_specialty` / `vw_kpis_by_provider` (`revenue_facturado_mes`); `sql/samples/04_billing_by_month.sql`; `RevenueBridge.csv`. |
| **Why it matters** | Misalignment flags billing lag or process gaps, not just “book more visits.” |

### T5 — Reconciliation gaps

| | |
|--|--|
| **Business question** | What **gaps** exist between **attended appointments** and **billing lines**? |
| **Metrics / methods** | Reconciliation buckets — [`metrics.md`](metrics.md) §9. |
| **BI / SQL direction** | `vw_revenue_bridge`; `sql/samples/05_reconciliation_attendance_vs_billing.sql`; `RevenueBridge.csv` in BI. |
| **Why it matters** | Surfaces administrative follow-up (missing charges, pending lines) without conflating clinical and billing workflows. |

### T6 — Prioritization under no-show risk

| | |
|--|--|
| **Business question** | At the documented decision point, **which appointments** merit prioritized outreach before the visit? |
| **Metrics / methods** | ML score is **not** a business KPI; it supports **ranking** — see [`ml/README.md`](../ml/README.md). No-show **rate** provides context from [`metrics.md`](metrics.md) §2. |
| **BI / SQL direction** | Same mart as BI; features from mart tables; no dedicated SQL view for score in MVP. |
| **Why it matters** | Converts analytic output into **ordered operational effort** (e.g. reminders) without automating actions in-repo. |

**Note (T1 and occupancy):** **Occupancy (proxy)** is defined in [`metrics.md`](metrics.md) §1 but **not materialized in a dedicated SQL view** today (see [`sql/README.md`](../sql/README.md)). Utilization reads can use volume and rate KPIs in existing views; BI may implement the proxy rule if needed.

---

## 2. Matrix — Question → KPI / SQL / BI / illustrative action

**Conventions:** “KPI” refers to [`metrics.md`](metrics.md) (numbered sections per metric). Views are listed in [`sql/README.md`](../sql/README.md). Export CSVs name consumption **roles**; column detail is in each `bi/` README.

| Id | Primary KPIs (reference) | SQL view / sample | Power BI (executive) | Tableau (diagnostic) | Illustrative operational action |
|----|--------------------------|---------------------|----------------------|-------------------------|--------------------------------|
| **T1** | No-show rate; cancellation; attended; daily trend ([`metrics.md`](metrics.md) §2–3, §5) | `vw_daily_kpis`; `sql/samples/03_attended_by_month.sql` | `DailyKpis.csv`: period trend | `DailyKpis.csv` / stories: trend & comparison | Review meeting; revisit targets if deviation persists |
| **T2** | No-show, cancel, productivity by specialty/channel ([`metrics.md`](metrics.md) §2–3, §11–12) | `vw_kpis_by_specialty`; samples `01`, `02` | `KpiBySpecialty.csv` | `KpiBySpecialty.csv`, `AppointmentBase.csv` | Focus channel/specialty underperforming; adjust capacity messaging |
| **T3** | Late cancel; cancel rate ([`metrics.md`](metrics.md) §4, §3) | `vw_appointment_base` (under-24-hours rule); sample `02` where applicable | Late cancel **out of** executive MVP canvas — [`bi/powerbi/README.md`](../bi/powerbi/README.md) | `AppointmentBase.csv`; [`bi/tableau/README.md`](../bi/tableau/README.md) | Tune reminders or cancel windows in critical segments |
| **T4** | Billed revenue; revenue per attended ([`metrics.md`](metrics.md) §6, §8) | `vw_kpis_by_specialty` / `vw_kpis_by_provider`; `sql/samples/04_billing_by_month.sql` | Revenue vs activity if designed (`RevenueBridge.csv`, KPIs) | `RevenueBridge.csv`, time series | Investigate billing lag vs activity |
| **T5** | Reconciliation ([`metrics.md`](metrics.md) §9) | `vw_revenue_bridge`; `sql/samples/05_reconciliation_attendance_vs_billing.sql` | Bridge / buckets via `RevenueBridge.csv` | Same: explore `reconciliation_bucket` | Prioritize issuance fixes or case review |
| **T6** | No-show rate (context); ML score = **prioritization** only | Mart tables per [`ml/README.md`](../ml/README.md); no score view in SQL | Does not replace KPIs; executive stays historical | Combined analysis possible offline | Rank list for **reminders** or manual review; **no** in-repo automation |

---

## 3. Decision use cases

Fixed pattern: **trigger** → **role** → **artifact** → **typical decision** → **honest limit**.

### UC1 — Executive rate monitoring

| Field | Content |
|-------|---------|
| **Trigger** | Sustained increase in **no-show rate** or **cancellation rate** in `vw_daily_kpis` / `DailyKpis.csv` vs prior period. |
| **Role** | Leadership / operations. |
| **Artifact** | Power BI executive (`bi/powerbi/`); validation aligned to [`metrics.md`](metrics.md). |
| **Typical decision** | Agree **focused review** (channel, specialty) and monitor next window. |
| **Limit** | Synthetic data; no universal “optimal” threshold; repo does not set policy. |

### UC2 — Specialty and channel diagnosis

| Field | Content |
|-------|---------|
| **Trigger** | Specialty or channel appears as outlier in `vw_kpis_by_specialty` or samples `01` / `02`. |
| **Role** | Service lead / front desk (operations). |
| **Artifact** | Tableau (`bi/tableau/`); `KpiBySpecialty.csv`, `AppointmentBase.csv`. |
| **Typical decision** | **Dig into** operational cause (slot, cancel reason) before changing capacity. |
| **Limit** | Observational association; not formal causal inference. |

### UC3 — Late cancellation

| Field | Content |
|-------|---------|
| **Trigger** | High **late cancellation rate** in segment (fewer than 24 hours before start; [`metrics.md`](metrics.md) §4). |
| **Role** | Reception / scheduling. |
| **Artifact** | Queries on `vw_appointment_base` + Tableau time/channel visuals. |
| **Typical decision** | Propose **reminder or window** adjustments (business decision); repo documents signal only. |
| **Limit** | Synthetic; real calibration needs production-like data. |

### UC4 — Care vs billing reconciliation

| Field | Content |
|-------|---------|
| **Trigger** | Growth in rows like **attended without billing** or pending in `vw_revenue_bridge`. |
| **Role** | Billing / administration. |
| **Artifact** | `sql/samples/05_reconciliation_attendance_vs_billing.sql`; `RevenueBridge.csv`. |
| **Typical decision** | **Prioritize** issuance fixes or case review; no automated collections from repo. |
| **Limit** | Strict **cash collected** not in MVP; see [`metrics.md`](metrics.md) §7. |

### UC5 — Prioritization under no-show risk (ML)

| Field | Content |
|-------|---------|
| **Trigger** | Need to **rank** pre-visit contacts with explicit criteria (demo/portfolio). |
| **Role** | Operations / scheduling (supervised). |
| **Artifact** | `scripts/train_no_show.py` → `ml/experiments/metrics.json`; [`ml/README.md`](../ml/README.md). |
| **Typical decision** | Use probability or rank to **order** reminders; threshold is business-owned. |
| **Limit** | Not a production service; weak performance possible on synthetic data; **do not** use for staff evaluation. |

---

## 4. Lightweight explainability checklist (no-show layer)

Use when presenting model results (interview, portfolio, internal note). Fill from `ml/experiments/metrics.json` and [`ml/README.md`](../ml/README.md).

| Field | What to state |
|-------|----------------|
| **Signal** | No-show probability (or rank); unit = **one appointment** at booking decision time. |
| **Universe** | Final status **ATTENDED** or **NO_SHOW**; cancel excluded from target. |
| **Decision point** | Immediately after **booking**; allowed vs leakage features in [`ml/README.md`](../ml/README.md). |
| **Technical evidence** | ROC-AUC, PR-AUC, Brier; **top-decile capture** (`top_decile` in `metrics.json`) as conceptual ops read. |
| **Local/global explanation** | Random Forest **importances** in `metrics.json`: column weight **in the model** (not causality). |
| **Use risks** | Confusing correlation with cause; scoring **people**; treating synthetic numbers as real. |
| **Suggested action type** | Prioritized **reminders** or list review; **no** automated execution in-repo. |

---

## 5. Documented today vs future technical work

### 5.1 In scope (current repo)

- KPI definitions and anchors in [`metrics.md`](metrics.md).
- SQLite mart, `vw_*` views, and samples per [`sql/README.md`](../sql/README.md).
- CSV exports and canvas guides in `bi/powerbi/` and `bi/tableau/`.
- Quality pipeline, executive KPI validation, **one** reproducible no-show experiment under `ml/experiments/`.
- This document and links from [`architecture.md`](architecture.md), [`problem.md`](problem.md), and [`README.md`](../README.md).

### 5.2 Possible future extensions (not committed)

| Topic | Notes |
|-------|--------|
| **Occupancy (proxy) in SQL or single measure** | Defined in metrics; dedicated view or unified BI measure pending. |
| **Cash collected** / treasury | Outside MVP; needs new facts or payment dates. |
| **Multi-site, fine slots, chained reschedules** | Outside MVP; see [`problem.md`](problem.md). |
| **Inference service**, **campaign automation** | Explicitly out; repo is reproducible demo. |
| **Other models** (e.g. cancellation) | Mentioned in [`ml/README.md`](../ml/README.md); not committed. |
| **Desktop workbooks** (`.pbix` / `.twbx`) | Local demo assets; not the contract of the repo. |

---

## 6. Quick reference — view ↔ trunk theme

| View | Primary trunk themes |
|------|----------------------|
| `vw_daily_kpis` | T1 — daily trend by appointment date |
| `vw_kpis_by_specialty` | T2, T4 — specialty cuts; billed revenue by month |
| `vw_kpis_by_provider` | T2, T4 — same by provider (operational) |
| `vw_appointment_base` | T2, T3 — enriched for cuts and temporal logic |
| `vw_revenue_bridge` | T4, T5 — reconciliation and revenue bridge per appointment |
