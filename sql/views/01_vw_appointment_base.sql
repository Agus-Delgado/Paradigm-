-- Vista base: cita enriquecida con dimensiones y claves de fecha (rol agenda).
DROP VIEW IF EXISTS vw_appointment_base;

CREATE VIEW vw_appointment_base AS
SELECT
  fa.appointment_id,
  fa.patient_id,
  fa.provider_id,
  fa.specialty_id,
  fa.coverage_id,
  fa.appointment_status_id,
  fa.booking_channel_id,
  fa.appointment_date,
  CAST(strftime('%Y%m%d', fa.appointment_date) AS INTEGER) AS appointment_date_key,
  fa.appointment_start,
  fa.booking_date,
  CAST(strftime('%Y%m%d', fa.booking_date) AS INTEGER) AS booking_date_key,
  fa.booking_ts,
  fa.cancellation_ts,
  CASE
    WHEN fa.cancellation_ts IS NULL OR fa.cancellation_ts = '' THEN NULL
    ELSE CAST(strftime('%Y%m%d', fa.cancellation_ts) AS INTEGER)
  END AS cancellation_date_key,
  fa.cancellation_reason_id,
  st.status_code,
  st.status_description,
  sp.specialty_name,
  cov.coverage_name,
  ch.channel_code,
  ch.channel_name AS booking_channel_name,
  p.provider_label,
  p.primary_specialty_id,
  cr.reason_code AS cancellation_reason_code,
  cr.reason_description AS cancellation_reason_description,
  dd.iso_week AS appointment_iso_week,
  dd.day_of_week AS appointment_day_of_week
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
JOIN dim_specialty sp ON fa.specialty_id = sp.specialty_id
JOIN dim_coverage cov ON fa.coverage_id = cov.coverage_id
JOIN dim_booking_channel ch ON fa.booking_channel_id = ch.booking_channel_id
JOIN dim_provider p ON fa.provider_id = p.provider_id
LEFT JOIN dim_cancellation_reason cr ON fa.cancellation_reason_id = cr.cancellation_reason_id
LEFT JOIN dim_date dd ON dd.date = fa.appointment_date;
