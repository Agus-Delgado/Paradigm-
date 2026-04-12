# Reporte de calidad de datos — Paradigm v2

- **Generado (UTC):** 2026-04-07 03:35:08Z
- **Base:** `C:/Users/agusd/OneDrive/Escritorio/Proyectos/Paradigm/data/processed/paradigm_mart.db`

| Severidad | ID | Nombre | Detalle | Métrica |
|-----------|-----|--------|---------|---------|
| ok | pragma_integrity | PRAGMA integrity_check | ok |  |
| ok | pragma_foreign_key_check | PRAGMA foreign_key_check | Sin violaciones de FK | 0 |
| ok | unique_fact_appointment | Claves únicas fact_appointment.appointment_id | Sin duplicados | 0 |
| ok | unique_fact_billing | Claves únicas fact_billing_line.billing_line_id | Sin duplicados | 0 |
| ok | nulls_fact_appointment | Nulos en columnas obligatorias (fact_appointment) | Ninguno | 0 |
| ok | nulls_fact_billing | Nulos en columnas obligatorias (fact_billing_line) | Ninguno | 0 |
| ok | dates_booking_le_appointment | booking_date <= appointment_date | Cumple | 0 |
| ok | state_cancellation_ts | Consistencia estado vs cancellation_ts | Canceladas sin ts: 0; otras con ts: 0 | 0 |
| ok | cancellation_reason_only_cancelled | cancellation_reason_id solo si estado cancelada | Cumple | 0 |
| ok | amounts_non_negative | Montos line_amount >= 0 | Cumple | 0 |
| ok | currency_ars | Moneda ARS en líneas de facturación | Todas ARS | 0 |
| ok | billing_fk_appointment | fact_billing_line.appointment_id existe en fact_appointment | Sin huérfanos | 0 |
| ok | appointment_date_in_dim_date | appointment_date presente en dim_date | Todas enlazadas | 0 |
| warn | attended_without_billing | Citas atendidas sin línea de facturación (brecha operativa) | Cantidad: 31 (esperado en sintético para demo de conciliación) | 31 |

## Leyenda

- **ok:** criterio cumplido.
- **warn:** regla de negocio o brecha esperada en datos sintéticos (revisar texto).
- **fail:** incumplimiento que debe corregirse antes de consumo BI.

