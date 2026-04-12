-- Citas atendidas por mes (fecha del turno)
SELECT
  strftime('%Y-%m', fa.appointment_date) AS year_month,
  COUNT(*) AS citas_atendidas
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
WHERE st.status_code = 'ATTENDED'
GROUP BY strftime('%Y-%m', fa.appointment_date)
ORDER BY year_month;
