-- Puente atención vs facturación por cita (grano cita).
-- reconciliation_bucket según docs/metric_definitions (conciliación operativa).
DROP VIEW IF EXISTS vw_revenue_bridge;

CREATE VIEW vw_revenue_bridge AS
SELECT
  fa.appointment_id,
  fa.appointment_date,
  fa.specialty_id,
  fa.provider_id,
  st.status_code,
  COALESCE(SUM(CASE WHEN bs.status_code = 'ISSUED' THEN fbl.line_amount ELSE 0 END), 0) AS revenue_issued,
  COALESCE(SUM(CASE WHEN bs.status_code = 'PENDING' THEN fbl.line_amount ELSE 0 END), 0) AS revenue_pending,
  COALESCE(SUM(CASE WHEN bs.status_code = 'PAID' THEN fbl.line_amount ELSE 0 END), 0) AS revenue_paid_proxy,
  COALESCE(SUM(CASE WHEN bs.status_code = 'VOID' THEN fbl.line_amount ELSE 0 END), 0) AS revenue_void,
  COALESCE(SUM(CASE WHEN bs.status_code != 'VOID' THEN fbl.line_amount ELSE 0 END), 0) AS revenue_total_non_void,
  COUNT(fbl.billing_line_id) AS billing_lines_count,
  CASE
    WHEN st.status_code = 'ATTENDED' AND COUNT(fbl.billing_line_id) = 0 THEN 'ATTENDED_NO_BILLING'
    WHEN st.status_code = 'ATTENDED' AND COALESCE(SUM(CASE WHEN bs.status_code = 'PENDING' THEN 1 ELSE 0 END), 0) > 0
      THEN 'ATTENDED_WITH_PENDING'
    WHEN st.status_code = 'ATTENDED' AND COUNT(fbl.billing_line_id) > 0 THEN 'ATTENDED_WITH_BILLING'
    ELSE 'NOT_APPLICABLE'
  END AS reconciliation_bucket
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
LEFT JOIN fact_billing_line fbl ON fa.appointment_id = fbl.appointment_id
LEFT JOIN dim_billing_status bs ON fbl.billing_status_id = bs.billing_status_id
GROUP BY
  fa.appointment_id,
  fa.appointment_date,
  fa.specialty_id,
  fa.provider_id,
  st.status_code;
