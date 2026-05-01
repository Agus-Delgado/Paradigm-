# Paradigm — KPI dictionary

## Principles

- Each KPI declares **time anchoring** (appointment date vs billing date vs cancellation timing).
- Definitions below are **MVP**; metrics marked as “later phase” are not required on the first dashboard.
- Table names align with [`data_dictionary.md`](data_dictionary.md) and the dimensional model.

## Time anchoring by KPI

| KPI | Primary date | Notes |
|-----|----------------|------|
| Occupancy (proxy) | Appointment date | Denominator uses proxy capacity rule (no slot-level model in MVP). |
| No-show rate | Appointment date | Denominator: attended + no-show (appointments that should occur). |
| Cancellation rate | Cancellation date **or** appointment date | Two different business questions—document which view uses which. |
| Late cancellation rate | Derived from timestamps | MVP threshold: **< 24 hours** before appointment start. |
| Attended appointments | Appointment date | Status = attended. |
| Billed revenue | Billing date (`billing_date`) | Do not use appointment date for billed-revenue P&L. |
| Cash collected | — | **Later phase** (no payment date in MVP). |
| Revenue per attended appointment | Explicit alignment | **MVP rule:** billed revenue from lines whose `billing_date` falls in the window, tied to attended appointments in the same analytic universe (see section rules). |
| Reconciliation | Appointment ↔ lines | Per attended appointment row. |
| Productivity by provider / specialty | Appointment date | Specialty = `specialty_id` on the appointment. |

---

## 1. Occupancy (proxy)

| Field | Content |
|-------|---------|
| **Definition** | Share of **appointments consuming operational capacity** vs **theoretical capacity** per provider per day. |
| **Numerator** | Appointments with **non-cancelled** status whose appointment date falls in the period during operating days/hours (exclude cancelled). |
| **Denominator** | **Proxy capacity:** documented constant (e.g. 16 appointments per provider per day in MVP). |
| **Source** | `fact_appointment`, `dim_appointment_status`, `dim_date` (appointment date). |
| **Limitation** | No **slot** or duration model; the KPI is **illustrative** and must be labeled as proxy in external narratives. |

## 2. No-show rate

| Field | Content |
|-------|---------|
| **Definition** | Share of no-shows among appointments that **should occur** (excludes cancelled). |
| **Numerator** | Count of appointments with **no-show** status. |
| **Denominator** | Count of **attended + no-show** in the period (same appointment date). |
| **Source** | `fact_appointment`, `dim_appointment_status`. |

## 3. Cancellation rate

| Field | Content |
|-------|---------|
| **Definition** | Share of **cancelled** appointments over an explicit universe. |
| **MVP variant — on agenda in period** | Numerator: cancelled with appointment date in period. Denominator: all appointments with appointment date in period. |
| **Source** | `fact_appointment`, appointment and cancellation dates. |

## 4. Late cancellation rate

| Field | Content |
|-------|---------|
| **Definition** | Among cancelled appointments, share where cancellation occurs **less than 24 hours** before `appointment_start` (datetime). |
| **Numerator** | Late cancellations. |
| **Denominator** | Total **cancelled** (recommended in MVP). |
| **Source** | `fact_appointment` with `cancellation_ts` and `appointment_start`. |

## 5. Attended appointments

| Field | Content |
|-------|---------|
| **Definition** | Count of appointments with **attended** status. |
| **Source** | `fact_appointment`. |

## 6. Billed revenue

| Field | Content |
|-------|---------|
| **Definition** | Sum of `line_amount` on lines with status other than **void** and `billing_date` in the period. |
| **Source** | `fact_billing_line`, `dim_billing_status`. |

## 7. Cash collected

| Field | Content |
|-------|---------|
| **Status** | **Not published in MVP** as real cash-collection finance (no payment date). |
| **Note** | If `PAID` is used later as a proxy, document it explicitly as **collection proxy**. |

## 8. Revenue per attended appointment

| Field | Content |
|-------|---------|
| **Definition** | Billed revenue associated with attended appointments / number of attended appointments in the analyzed window. |
| **MVP rule** | Sum valid lines linked to **attended** appointments; exclude void lines. |

## 9. Reconciliation — care vs billing

| Field | Content |
|-------|---------|
| **Definition** | For each attended appointment: presence of line(s) **issued/paid** vs **pending** vs **no line**. |
| **Source** | Join `fact_appointment` ↔ `fact_billing_line`. |

## 10. Operational productivity by provider

| Field | Content |
|-------|---------|
| **Definition** | Attended appointments by `provider_id` and period (day or week). |
| **Ethics** | **Operational** metric, not clinical performance evaluation. |

## 11. Productivity by specialty

| Field | Content |
|-------|---------|
| **Definition** | Attended appointments grouped by `specialty_id` on the **appointment** (not only provider primary specialty). |

## 12. Distribution by booking channel

| Field | Content |
|-------|---------|
| **Definition** | Channel mix in appointment volume (by `booking_date` or `appointment_date` depending on the question). |

---

## Global MVP rules

- **Currency:** ARS only in synthetic billing lines.
- **Appointment statuses:** mutually exclusive (attended / cancelled / no-show).
- **Billed revenue:** anchored to **`billing_date`**, not appointment date.
