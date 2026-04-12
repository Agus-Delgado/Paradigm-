-- KPIs diarios por fecha del turno (appointment_date).
-- no_show_rate = no_show / (attended + no_show) según docs/metric_definitions.md
-- cancellation_rate = canceladas / todas las citas con turno ese día
DROP VIEW IF EXISTS vw_daily_kpis;

CREATE VIEW vw_daily_kpis AS
SELECT
  fa.appointment_date,
  CAST(strftime('%Y%m%d', fa.appointment_date) AS INTEGER) AS appointment_date_key,
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
  END AS no_show_rate,
  CASE
    WHEN COUNT(*) > 0
    THEN ROUND(1.0 * SUM(CASE WHEN st.status_code = 'CANCELLED' THEN 1 ELSE 0 END) / COUNT(*), 4)
  END AS cancellation_rate
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
GROUP BY fa.appointment_date;
