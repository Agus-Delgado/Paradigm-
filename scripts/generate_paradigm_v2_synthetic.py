"""
Genera el dataset sintético mínimo viable (MVP) de Paradigm v2 en data/synthetic/.
Salida alineada a docs/data_dictionary.md. Semilla fija para reproducibilidad.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_APPOINTMENTS = 520
START = "2024-01-02"
END = "2025-02-28"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def build_dim_date() -> pd.DataFrame:
    dr = pd.date_range(START, END, freq="D")
    rows = []
    for d in dr:
        di = d.date()
        rows.append(
            {
                "date_key": int(di.strftime("%Y%m%d")),
                "date": di.isoformat(),
                "year": d.year,
                "month": d.month,
                "iso_week": int(d.isocalendar()[1]),
                "day_of_week": d.isoweekday(),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    rng = np.random.default_rng(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dim_specialty = pd.DataFrame(
        {
            "specialty_id": range(1, 7),
            "specialty_name": [
                "Clínica médica",
                "Cardiología",
                "Dermatología",
                "Pediatría",
                "Ginecología",
                "Traumatología",
            ],
        }
    )

    dim_coverage = pd.DataFrame(
        {
            "coverage_id": range(1, 7),
            "coverage_name": [
                "OSDE",
                "Swiss Medical",
                "Galeno",
                "PAMI",
                "Sancor Salud",
                "Particular",
            ],
        }
    )

    dim_appointment_status = pd.DataFrame(
        {
            "appointment_status_id": [1, 2, 3],
            "status_code": ["ATTENDED", "CANCELLED", "NO_SHOW"],
            "status_description": ["Atendida", "Cancelada", "No-show"],
        }
    )

    dim_booking_channel = pd.DataFrame(
        {
            "booking_channel_id": [1, 2, 3],
            "channel_code": ["WEB", "PHONE", "RECEPTION"],
            "channel_name": ["Web / app", "Telefónico", "Recepción"],
        }
    )

    dim_billing_status = pd.DataFrame(
        {
            "billing_status_id": [1, 2, 3, 4],
            "status_code": ["ISSUED", "PENDING", "VOID", "PAID"],
            "status_description": [
                "Facturado emitido",
                "Pendiente de facturación",
                "Anulado",
                "Pagado (proxy MVP)",
            ],
        }
    )

    dim_cancellation_reason = pd.DataFrame(
        {
            "cancellation_reason_id": [1, 2, 3, 4],
            "reason_code": ["PATIENT", "SCHEDULE", "ADMIN", "OTHER"],
            "reason_description": [
                "Paciente solicitó",
                "Cambio de agenda del centro",
                "Motivo administrativo",
                "Otro / no informado",
            ],
        }
    )

    n_patients = 72
    dim_patient = pd.DataFrame(
        {
            "patient_id": range(1, n_patients + 1),
            "age_band": rng.choice(
                ["18-34", "35-54", "55-69", "70+"], size=n_patients, p=[0.28, 0.38, 0.24, 0.10]
            ),
            "sex": rng.choice(["F", "M", "X"], size=n_patients, p=[0.52, 0.46, 0.02]),
            "coverage_id": rng.integers(1, 7, size=n_patients),
        }
    )

    # 8 proveedores con especialidad principal
    primary = np.array([1, 1, 2, 3, 4, 5, 6, 2])
    dim_provider = pd.DataFrame(
        {
            "provider_id": range(1, 9),
            "provider_label": [f"PR-{i:02d}" for i in range(1, 9)],
            "primary_specialty_id": primary,
        }
    )

    dim_date = build_dim_date()

    business_days = pd.bdate_range(START, END)
    status_weights = np.array([0.70, 0.18, 0.12])
    channel_weights = np.array([0.35, 0.40, 0.25])

    appointments: list[dict] = []
    billing_lines: list[dict] = []
    line_counter = 1

    for i in range(N_APPOINTMENTS):
        apt_num = i + 1
        appointment_id = f"APT-{apt_num:05d}"

        d = business_days[int(rng.integers(0, len(business_days)))]
        day = d.date()
        hour = int(rng.integers(8, 18))
        minute = int(rng.choice([0, 15, 30, 45]))
        appointment_start = datetime.combine(day, datetime.min.time()) + timedelta(
            hours=hour, minutes=minute
        )

        pid = int(rng.integers(1, n_patients + 1))
        prov_id = int(rng.integers(1, 9))
        specialty_id = int(primary[prov_id - 1])
        cov_id = int(rng.integers(1, 7))
        channel_id = int(rng.choice([1, 2, 3], p=channel_weights))

        lead_days = int(min(60, max(0, round(rng.gamma(2.5, 5.0)))))
        booking_ts = appointment_start - timedelta(days=lead_days)
        # Ajuste simple: si booking cae en fin de semana, empujar a lunes siguiente 9h
        while booking_ts.weekday() >= 5:
            booking_ts += timedelta(days=1)
        booking_ts = booking_ts.replace(hour=int(rng.integers(9, 19)), minute=int(rng.choice([0, 15, 30])))

        booking_date = booking_ts.date().isoformat()

        status_roll = rng.choice([1, 2, 3], p=status_weights)
        cancellation_ts: str | None = None
        cancel_reason_id: int | None = None

        if status_roll == 2:
            cancel_reason_id = int(rng.integers(1, 5))
            is_late = rng.random() < 0.35
            if is_late:
                delta_h = rng.uniform(0.5, 23.0)
                c_ts = appointment_start - timedelta(hours=float(delta_h))
                if c_ts < booking_ts:
                    c_ts = booking_ts + timedelta(hours=1)
                cancellation_ts = _iso(c_ts)
            else:
                span = max((appointment_start - booking_ts).total_seconds() - 3600, 3600.0)
                offset = rng.uniform(0, span)
                c_ts = booking_ts + timedelta(seconds=offset)
                if c_ts >= appointment_start:
                    c_ts = appointment_start - timedelta(hours=2)
                cancellation_ts = _iso(c_ts)

        appointments.append(
            {
                "appointment_id": appointment_id,
                "patient_id": pid,
                "provider_id": prov_id,
                "specialty_id": specialty_id,
                "coverage_id": cov_id,
                "appointment_status_id": status_roll,
                "booking_channel_id": channel_id,
                "appointment_date": day.isoformat(),
                "appointment_start": _iso(appointment_start),
                "booking_date": booking_date,
                "booking_ts": _iso(booking_ts),
                "cancellation_ts": cancellation_ts if status_roll == 2 else "",
                "cancellation_reason_id": cancel_reason_id if status_roll == 2 else "",
            }
        )

        # Facturación: solo citas atendidas (y algunas brechas intencionales)
        if status_roll == 1:
            skip_bill = rng.random() < 0.06
            if not skip_bill:
                n_lines = int(rng.choice([1, 2], p=[0.82, 0.18]))
                for _ in range(n_lines):
                    amt = float(rng.uniform(6500, 28000))
                    bstat = int(rng.choice([1, 2, 4], p=[0.42, 0.18, 0.40]))
                    delay_days = int(rng.integers(0, 5))
                    bdate = (day + timedelta(days=delay_days)).isoformat()
                    if bstat == 2:
                        bdate = day.isoformat()
                    billing_lines.append(
                        {
                            "billing_line_id": f"BLN-{line_counter:05d}",
                            "appointment_id": appointment_id,
                            "billing_date": bdate,
                            "line_amount": round(amt, 2),
                            "billing_status_id": bstat,
                            "currency": "ARS",
                        }
                    )
                    line_counter += 1
        elif status_roll == 3 and rng.random() < 0.12:
            # Cargo simbólico / pendiente en no-show (minoría)
            billing_lines.append(
                {
                    "billing_line_id": f"BLN-{line_counter:05d}",
                    "appointment_id": appointment_id,
                    "billing_date": day.isoformat(),
                    "line_amount": round(float(rng.uniform(2000, 5000)), 2),
                    "billing_status_id": 2,
                    "currency": "ARS",
                }
            )
            line_counter += 1

    fact_appointment = pd.DataFrame(appointments)
    fact_billing_line = pd.DataFrame(billing_lines)

    # Guardar
    dim_date.to_csv(OUTPUT_DIR / "dim_date.csv", index=False)
    dim_specialty.to_csv(OUTPUT_DIR / "dim_specialty.csv", index=False)
    dim_coverage.to_csv(OUTPUT_DIR / "dim_coverage.csv", index=False)
    dim_appointment_status.to_csv(OUTPUT_DIR / "dim_appointment_status.csv", index=False)
    dim_booking_channel.to_csv(OUTPUT_DIR / "dim_booking_channel.csv", index=False)
    dim_billing_status.to_csv(OUTPUT_DIR / "dim_billing_status.csv", index=False)
    dim_cancellation_reason.to_csv(OUTPUT_DIR / "dim_cancellation_reason.csv", index=False)
    dim_patient.to_csv(OUTPUT_DIR / "dim_patient.csv", index=False)
    dim_provider.to_csv(OUTPUT_DIR / "dim_provider.csv", index=False)
    fact_appointment.to_csv(OUTPUT_DIR / "fact_appointment.csv", index=False)
    fact_billing_line.to_csv(OUTPUT_DIR / "fact_billing_line.csv", index=False)

    readme = OUTPUT_DIR / "README.md"
    readme.write_text(
        """# Dataset sintético Paradigm v2 (MVP)

**Uso:** modelado dimensional y futura capa SQL; datos **ficticios**.

**Regeneración:**

```bash
python scripts/generate_paradigm_v2_synthetic.py
```

**Parámetros:** `SEED=42`, `N_APPOINTMENTS={n}`, rango de fechas `{s}`–`{e}`.

Ver [`docs/data_dictionary.md`](../../docs/data_dictionary.md).
""".format(n=N_APPOINTMENTS, s=START, e=END),
        encoding="utf-8",
    )

    print(f"Escrito en {OUTPUT_DIR} ({len(fact_appointment)} citas, {len(fact_billing_line)} líneas de facturación).")


if __name__ == "__main__":
    main()
