-- Agregación mensual por especialidad operativa (fecha del turno).
-- revenue_facturado_mes: suma de líneas con billing_date en ese mes y misma especialidad (vía cita);
--   puede diferir del mes del turno si la factura se postea otro mes (documentado en sql/README.md).
DROP VIEW IF EXISTS vw_kpis_by_specialty;

CREATE VIEW vw_kpis_by_specialty AS
SELECT
  apt.year_month,
  apt.specialty_id,
  sp.specialty_name,
  apt.appointments_total,
  apt.attended_count,
  apt.cancelled_count,
  apt.no_show_count,
  apt.no_show_rate,
  COALESCE(rev.revenue_facturado_mes, 0) AS revenue_facturado_mes
FROM (
  SELECT
    strftime('%Y-%m', fa.appointment_date) AS year_month,
    fa.specialty_id,
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
  GROUP BY strftime('%Y-%m', fa.appointment_date), fa.specialty_id
) apt
JOIN dim_specialty sp ON apt.specialty_id = sp.specialty_id
LEFT JOIN (
  SELECT
    strftime('%Y-%m', fbl.billing_date) AS year_month,
    fa.specialty_id,
    SUM(CASE WHEN bs.status_code != 'VOID' THEN fbl.line_amount ELSE 0 END) AS revenue_facturado_mes
  FROM fact_billing_line fbl
  JOIN fact_appointment fa ON fbl.appointment_id = fa.appointment_id
  JOIN dim_billing_status bs ON fbl.billing_status_id = bs.billing_status_id
  GROUP BY strftime('%Y-%m', fbl.billing_date), fa.specialty_id
) rev ON rev.year_month = apt.year_month AND rev.specialty_id = apt.specialty_id;
