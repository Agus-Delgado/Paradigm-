# Paradigm — Data dictionary (synthetic MVP)

**Source:** files in [`data/synthetic/`](../data/synthetic/README.md).  
**Regeneration:** `python scripts/generate_paradigm_v2_synthetic.py` (fixed seed).

All identifiers are **fictitious**. They do not represent real people.

---

## Conventions

- **Dates:** `YYYY-MM-DD` in CSV; timestamps in ISO 8601 (`...T...`, fictional local time).
- **Keys:** integers (`*_id`) except `appointment_id` and `billing_line_id`, which use a text prefix for human-readable traceability.
- **Currency:** `ARS` only on billing lines.

---

## dim_date.csv

| Column | Type | Description |
|--------|------|-------------|
| date_key | int | Integer `YYYYMMDD` (logical PK). |
| date | date | Calendar date. |
| year | int | Year. |
| month | int | Month (1–12). |
| iso_week | int | ISO week. |
| day_of_week | int | 1 = Monday … 7 = Sunday. |

---

## dim_specialty.csv

| Column | Type | Description |
|--------|------|-------------|
| specialty_id | int | PK. |
| specialty_name | str | Service specialty name (operational cut). |

---

## dim_coverage.csv

| Column | Type | Description |
|--------|------|-------------|
| coverage_id | int | PK. |
| coverage_name | str | Payer / plan label (e.g. insurer, self-pay). |

---

## dim_appointment_status.csv

| Column | Type | Description |
|--------|------|-------------|
| appointment_status_id | int | PK. |
| status_code | str | `ATTENDED`, `CANCELLED`, `NO_SHOW`. |
| status_description | str | Human-readable label. |

---

## dim_booking_channel.csv

| Column | Type | Description |
|--------|------|-------------|
| booking_channel_id | int | PK. |
| channel_code | str | `WEB`, `PHONE`, `RECEPTION`. |
| channel_name | str | BI label. |

---

## dim_billing_status.csv

| Column | Type | Description |
|--------|------|-------------|
| billing_status_id | int | PK. |
| status_code | str | `ISSUED`, `PENDING`, `VOID`, `PAID`. |
| status_description | str | `PAID` acts as **collection proxy** in MVP (no payment date). |

---

## dim_cancellation_reason.csv

| Column | Type | Description |
|--------|------|-------------|
| cancellation_reason_id | int | PK. |
| reason_code | str | Short code. |
| reason_description | str | Text for cancellation analysis. |

---

## dim_patient.csv

| Column | Type | Description |
|--------|------|-------------|
| patient_id | int | Fictitious PK. |
| age_band | str | Aggregated age band. |
| sex | str | `F`, `M`, `X` (fictional). |
| coverage_id | int | FK → `dim_coverage` (baseline profile; appointment may carry snapshot). |

---

## dim_provider.csv

| Column | Type | Description |
|--------|------|-------------|
| provider_id | int | Fictitious PK. |
| provider_label | str | Initials or anonymized label. |
| primary_specialty_id | int | FK → `dim_specialty` (descriptive; **booked service** is on the appointment). |

---

## fact_appointment.csv

**Grain:** one row per **appointment**.

| Column | Type | Description |
|--------|------|-------------|
| appointment_id | str | Unique id (e.g. `APT-NNNNN`). |
| patient_id | int | FK → `dim_patient`. |
| provider_id | int | FK → `dim_provider`. |
| specialty_id | int | FK → `dim_specialty` (**operational** specialty for the visit). |
| coverage_id | int | FK → `dim_coverage` (as of booking). |
| appointment_status_id | int | FK → `dim_appointment_status`. |
| booking_channel_id | int | FK → `dim_booking_channel`. |
| appointment_date | date | Appointment day (schedule role). |
| appointment_start | str | Scheduled start (ISO datetime). |
| booking_date | date | Booking day (no time). |
| booking_ts | str | Booking timestamp (ISO). |
| cancellation_ts | str | Nullable; cancellation timestamp. |
| cancellation_reason_id | int | Nullable; FK when status is cancelled. |

**Rules:** `booking_date` ≤ `appointment_date`. If cancelled, `cancellation_ts` is non-null. If attended or no-show, `cancellation_ts` is null.

---

## fact_billing_line.csv

**Grain:** one row per **billing line**.

| Column | Type | Description |
|--------|------|-------------|
| billing_line_id | str | Unique id (e.g. `BLN-NNNNN`). |
| appointment_id | str | Nullable; FK to attended/pending appointment. |
| billing_date | date | **Anchor** for billed revenue (do not confuse with appointment date). |
| line_amount | float | Amount in ARS (synthetic). |
| billing_status_id | int | FK → `dim_billing_status`. |
| currency | str | `ARS`. |

---

## Referential integrity (logical)

- `fact_appointment.patient_id` → `dim_patient.patient_id`
- `fact_appointment.provider_id` → `dim_provider.provider_id`
- `fact_appointment.specialty_id` → `dim_specialty.specialty_id`
- `fact_appointment.coverage_id` → `dim_coverage.coverage_id`
- `fact_appointment.appointment_status_id` → `dim_appointment_status.appointment_status_id`
- `fact_appointment.booking_channel_id` → `dim_booking_channel.booking_channel_id`
- `fact_billing_line.appointment_id` → `fact_appointment.appointment_id` (when non-null)
- `fact_billing_line.billing_status_id` → `dim_billing_status.billing_status_id`

Fact dates (`appointment_date`, `billing_date`) join semantically to `dim_date.date` / `date_key` in the SQL layer.
