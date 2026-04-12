-- No-show rate por especialidad (fecha del turno, todo el historial cargado)
-- Denominador: atendidas + no-shows (definición métrica)
SELECT
  sp.specialty_name,
  SUM(CASE WHEN st.status_code = 'NO_SHOW' THEN 1 ELSE 0 END) AS no_shows,
  SUM(CASE WHEN st.status_code = 'ATTENDED' THEN 1 ELSE 0 END) AS attended,
  ROUND(
    1.0 * SUM(CASE WHEN st.status_code = 'NO_SHOW' THEN 1 ELSE 0 END)
    / NULLIF(SUM(CASE WHEN st.status_code IN ('ATTENDED', 'NO_SHOW') THEN 1 ELSE 0 END), 0),
    4
  ) AS no_show_rate
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
JOIN dim_specialty sp ON fa.specialty_id = sp.specialty_id
GROUP BY sp.specialty_id, sp.specialty_name
ORDER BY no_show_rate DESC;
