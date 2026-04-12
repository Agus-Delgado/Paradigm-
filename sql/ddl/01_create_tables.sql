-- Paradigm v2 — esquema mart (SQLite)
-- Fuente: data/synthetic/*.csv — ver docs/data_dictionary.md
-- Ejecutar vía scripts/build_sqlite_mart.py (PRAGMA foreign_keys=ON)

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS fact_billing_line;
DROP TABLE IF EXISTS fact_appointment;
DROP TABLE IF EXISTS dim_provider;
DROP TABLE IF EXISTS dim_patient;
DROP TABLE IF EXISTS dim_cancellation_reason;
DROP TABLE IF EXISTS dim_billing_status;
DROP TABLE IF EXISTS dim_booking_channel;
DROP TABLE IF EXISTS dim_appointment_status;
DROP TABLE IF EXISTS dim_coverage;
DROP TABLE IF EXISTS dim_specialty;
DROP TABLE IF EXISTS dim_date;

PRAGMA foreign_keys = ON;

CREATE TABLE dim_date (
  date_key INTEGER NOT NULL PRIMARY KEY,
  date TEXT NOT NULL UNIQUE,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  iso_week INTEGER NOT NULL,
  day_of_week INTEGER NOT NULL
);

CREATE TABLE dim_specialty (
  specialty_id INTEGER NOT NULL PRIMARY KEY,
  specialty_name TEXT NOT NULL
);

CREATE TABLE dim_coverage (
  coverage_id INTEGER NOT NULL PRIMARY KEY,
  coverage_name TEXT NOT NULL
);

CREATE TABLE dim_appointment_status (
  appointment_status_id INTEGER NOT NULL PRIMARY KEY,
  status_code TEXT NOT NULL UNIQUE,
  status_description TEXT NOT NULL
);

CREATE TABLE dim_booking_channel (
  booking_channel_id INTEGER NOT NULL PRIMARY KEY,
  channel_code TEXT NOT NULL UNIQUE,
  channel_name TEXT NOT NULL
);

CREATE TABLE dim_billing_status (
  billing_status_id INTEGER NOT NULL PRIMARY KEY,
  status_code TEXT NOT NULL UNIQUE,
  status_description TEXT NOT NULL
);

CREATE TABLE dim_cancellation_reason (
  cancellation_reason_id INTEGER NOT NULL PRIMARY KEY,
  reason_code TEXT NOT NULL,
  reason_description TEXT NOT NULL
);

CREATE TABLE dim_patient (
  patient_id INTEGER NOT NULL PRIMARY KEY,
  age_band TEXT NOT NULL,
  sex TEXT NOT NULL,
  coverage_id INTEGER NOT NULL,
  FOREIGN KEY (coverage_id) REFERENCES dim_coverage (coverage_id)
);

CREATE TABLE dim_provider (
  provider_id INTEGER NOT NULL PRIMARY KEY,
  provider_label TEXT NOT NULL,
  primary_specialty_id INTEGER NOT NULL,
  FOREIGN KEY (primary_specialty_id) REFERENCES dim_specialty (specialty_id)
);

CREATE TABLE fact_appointment (
  appointment_id TEXT NOT NULL PRIMARY KEY,
  patient_id INTEGER NOT NULL,
  provider_id INTEGER NOT NULL,
  specialty_id INTEGER NOT NULL,
  coverage_id INTEGER NOT NULL,
  appointment_status_id INTEGER NOT NULL,
  booking_channel_id INTEGER NOT NULL,
  appointment_date TEXT NOT NULL,
  appointment_start TEXT NOT NULL,
  booking_date TEXT NOT NULL,
  booking_ts TEXT NOT NULL,
  cancellation_ts TEXT,
  cancellation_reason_id INTEGER,
  FOREIGN KEY (patient_id) REFERENCES dim_patient (patient_id),
  FOREIGN KEY (provider_id) REFERENCES dim_provider (provider_id),
  FOREIGN KEY (specialty_id) REFERENCES dim_specialty (specialty_id),
  FOREIGN KEY (coverage_id) REFERENCES dim_coverage (coverage_id),
  FOREIGN KEY (appointment_status_id) REFERENCES dim_appointment_status (appointment_status_id),
  FOREIGN KEY (booking_channel_id) REFERENCES dim_booking_channel (booking_channel_id),
  FOREIGN KEY (cancellation_reason_id) REFERENCES dim_cancellation_reason (cancellation_reason_id)
);

CREATE TABLE fact_billing_line (
  billing_line_id TEXT NOT NULL PRIMARY KEY,
  appointment_id TEXT,
  billing_date TEXT NOT NULL,
  line_amount REAL NOT NULL,
  billing_status_id INTEGER NOT NULL,
  currency TEXT NOT NULL,
  FOREIGN KEY (appointment_id) REFERENCES fact_appointment (appointment_id),
  FOREIGN KEY (billing_status_id) REFERENCES dim_billing_status (billing_status_id)
);

CREATE INDEX idx_fact_appointment_date ON fact_appointment (appointment_date);
CREATE INDEX idx_fact_appointment_specialty ON fact_appointment (specialty_id);
CREATE INDEX idx_fact_appointment_provider ON fact_appointment (provider_id);
CREATE INDEX idx_fact_appointment_status ON fact_appointment (appointment_status_id);
CREATE INDEX idx_fact_billing_line_appointment ON fact_billing_line (appointment_id);
CREATE INDEX idx_fact_billing_line_date ON fact_billing_line (billing_date);
