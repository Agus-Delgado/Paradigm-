# Paradigm v2 — Diccionario de datos (MVP sintético)

**Origen:** archivos en [`data/synthetic/`](../data/synthetic/README.md).  
**Regeneración:** `python scripts/generate_paradigm_v2_synthetic.py` (semilla fija).

Todos los identificadores son **ficticios**. No representan personas reales.

---

## Convenciones

- **Fechas:** `YYYY-MM-DD` en CSV; timestamps en ISO 8601 (`...T...` hora local ficticia).
- **Claves:** enteros (`*_id`) salvo `appointment_id` y `billing_line_id` con prefijo textual para trazabilidad en lectura humana.
- **Moneda:** `ARS` única en líneas de facturación.

---

## dim_date.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| date_key | int | Entero `YYYYMMDD` (PK lógica). |
| date | date | Fecha calendario. |
| year | int | Año. |
| month | int | Mes (1–12). |
| iso_week | int | Semana ISO. |
| day_of_week | int | 1=lunes … 7=domingo. |

---

## dim_specialty.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| specialty_id | int | PK. |
| specialty_name | str | Nombre de la especialidad del **servicio** (corte operativo). |

---

## dim_coverage.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| coverage_id | int | PK. |
| coverage_name | str | Obra social / prepaga / particular. |

---

## dim_appointment_status.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| appointment_status_id | int | PK. |
| status_code | str | `ATTENDED`, `CANCELLED`, `NO_SHOW`. |
| status_description | str | Texto legible. |

---

## dim_booking_channel.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| booking_channel_id | int | PK. |
| channel_code | str | `WEB`, `PHONE`, `RECEPTION`. |
| channel_name | str | Etiqueta para BI. |

---

## dim_billing_status.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| billing_status_id | int | PK. |
| status_code | str | `ISSUED`, `PENDING`, `VOID`, `PAID`. |
| status_description | str | `PAID` actúa como **proxy** de cobro en MVP (sin fecha de pago). |

---

## dim_cancellation_reason.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| cancellation_reason_id | int | PK. |
| reason_code | str | Código corto. |
| reason_description | str | Texto para análisis de cancelaciones. |

---

## dim_patient.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| patient_id | int | PK ficticia. |
| age_band | str | Banda etaria (agregada). |
| sex | str | `F`, `M`, `X` (ficticio). |
| coverage_id | int | FK → `dim_coverage` (perfil base; la cita puede llevar snapshot). |

---

## dim_provider.csv

| Columna | Tipo | Descripción |
|---------|------|-------------|
| provider_id | int | PK ficticia. |
| provider_label | str | Iniciales o etiqueta anonimizada. |
| primary_specialty_id | int | FK → `dim_specialty` (atributo descriptivo; el **servicio del turno** va en la cita). |

---

## fact_appointment.csv

Grano: **una fila por cita**.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| appointment_id | str | Identificador único (p. ej. `APT-NNNNN`). |
| patient_id | int | FK → `dim_patient`. |
| provider_id | int | FK → `dim_provider`. |
| specialty_id | int | FK → `dim_specialty` (**especialidad operativa** del turno). |
| coverage_id | int | FK → `dim_coverage` (vigente al momento de la reserva). |
| appointment_status_id | int | FK → `dim_appointment_status`. |
| booking_channel_id | int | FK → `dim_booking_channel`. |
| appointment_date | date | Día del turno (rol agenda). |
| appointment_start | str | Inicio programado (ISO datetime). |
| booking_date | date | Día de la reserva (sin hora). |
| booking_ts | str | Timestamp de reserva (ISO). |
| cancellation_ts | str | Nullable; timestamp de cancelación. |
| cancellation_reason_id | int | Nullable; FK si estado = cancelada. |

**Reglas:** `booking_date` ≤ `appointment_date`. Si estado = cancelada, `cancellation_ts` no nulo. Si no-show o atendida, `cancellation_ts` nulo.

---

## fact_billing_line.csv

Grano: **una fila por línea de cargo**.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| billing_line_id | str | Identificador único (p. ej. `BLN-NNNNN`). |
| appointment_id | str | Nullable; FK a cita atendida o pendiente. |
| billing_date | date | **Anclaje** para ingreso facturado (no confundir con fecha de turno). |
| line_amount | float | Monto en ARS (sintético). |
| billing_status_id | int | FK → `dim_billing_status`. |
| currency | str | `ARS`. |

---

## Relaciones lógicas (integridad referencial)

- `fact_appointment.patient_id` → `dim_patient.patient_id`
- `fact_appointment.provider_id` → `dim_provider.provider_id`
- `fact_appointment.specialty_id` → `dim_specialty.specialty_id`
- `fact_appointment.coverage_id` → `dim_coverage.coverage_id`
- `fact_appointment.appointment_status_id` → `dim_appointment_status.appointment_status_id`
- `fact_appointment.booking_channel_id` → `dim_booking_channel.booking_channel_id`
- `fact_billing_line.appointment_id` → `fact_appointment.appointment_id` (cuando no nulo)
- `fact_billing_line.billing_status_id` → `dim_billing_status.billing_status_id`

Las fechas de hechos (`appointment_date`, `billing_date`) enlazan semánticamente con `dim_date.date` / `date_key` en la capa SQL (próxima fase).
