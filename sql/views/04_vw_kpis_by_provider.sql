-- Igual que vw_kpis_by_specialty pero por proveedor (métricas operativas; no calidad clínica).
DROP VIEW IF EXISTS vw_kpis_by_provider;

CREATE VIEW vw_kpis_by_provider AS
SELECT
  apt.year_month,
  apt.provider_id,
  p.provider_label,
  apt.primary_specialty_id,
  apt.appointments_total,
  apt.attended_count,
  apt.cancelled_count,
  apt.no_show_count,
  apt.no_show_rate,
  COALESCE(rev.revenue_facturado_mes, 0) AS revenue_facturado_mes
FROM (
  SELECT
    strftime('%Y-%m', fa.appointment_date) AS year_month,
    fa.provider_id,
    dp.primary_specialty_id,
    COUNT(*) AS appointments_total,
    SUM(CASE WHEN st.status_code = 'ATTENDED' THEN 1 ELSE 0 END) AS attended_count,
    SUM(CASE WHEN st.status_code = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_count,
    SUM(CASE WHEN st.status_code = 'NO_SHOW' THEN 1 ELSE 0 END) AS no_show_count,
    CASE
      WHEN SUM(CASE WHEN st.status_code IN ('ATTENDED', 'NO_SHOW') THEN 1 ELSE 0 END) > 0
      THEN ROUND(
        1.0 * SUM(CASE WHEN st.status_code = 'NO_SHOW' THEN 1 ELSE 0 END)
        / SUM(CASE WHEN st.status_code IN ('ATTENDED', 'NO_SHOW') THEN 1 ELSE 0 END),
        4
      )
    END AS no_show_rate
  FROM fact_appointment fa
  JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
  JOIN dim_provider dp ON fa.provider_id = dp.provider_id
  GROUP BY strftime('%Y-%m', fa.appointment_date), fa.provider_id, dp.primary_specialty_id
) apt
JOIN dim_provider p ON apt.provider_id = p.provider_id
LEFT JOIN (
  SELECT
    strftime('%Y-%m', fbl.billing_date) AS year_month,
    fa.provider_id,
    SUM(CASE WHEN bs.status_code != 'VOID' THEN fbl.line_amount ELSE 0 END) AS revenue_facturado_mes
  FROM fact_billing_line fbl
  JOIN fact_appointment fa ON fbl.appointment_id = fa.appointment_id
  JOIN dim_billing_status bs ON fbl.billing_status_id = bs.billing_status_id
  GROUP BY strftime('%Y-%m', fbl.billing_date), fa.provider_id
) rev ON rev.year_month = apt.year_month AND rev.provider_id = apt.provider_id;
