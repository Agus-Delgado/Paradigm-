-- Cancelaciones por canal de reserva (volumen y tasa sobre total de citas en canal)
SELECT
  ch.channel_name,
  COUNT(*) AS citas_total,
  SUM(CASE WHEN st.status_code = 'CANCELLED' THEN 1 ELSE 0 END) AS canceladas,
  ROUND(
    1.0 * SUM(CASE WHEN st.status_code = 'CANCELLED' THEN 1 ELSE 0 END) / COUNT(*),
    4
  ) AS tasa_cancelacion
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
JOIN dim_booking_channel ch ON fa.booking_channel_id = ch.booking_channel_id
GROUP BY ch.booking_channel_id, ch.channel_name
ORDER BY canceladas DESC;
