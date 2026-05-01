"""
Genera datos sintéticos reproducibles para la demo de consultorio médico.
Salida: legacy/data/sample/medical_clinic/*.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PATIENTS = 300
N_PROFESSIONALS = 12
N_APPOINTMENTS = 2000

# Mayor peso a Clínica médica y Cardiología al asignar turnos (suma = 1.0)
SPECIALTY_APPOINTMENT_WEIGHTS: dict[str, float] = {
    "Clínica médica": 0.34,
    "Cardiología": 0.26,
    "Dermatología": 0.08,
    "Traumatología": 0.08,
    "Ginecología": 0.08,
    "Neurología": 0.08,
    "Pediatría": 0.08,
}

COBERTURAS = [
    ("OSDE", 0.22),
    ("Swiss Medical", 0.18),
    ("Galeno", 0.14),
    ("PAMI", 0.12),
    ("OSECAC", 0.10),
    ("Sancor Salud", 0.08),
    ("Particular", 0.10),
    ("Medifé", 0.06),
]

LOCALIDADES = [
    ("CABA", 0.42),
    ("Zona Norte", 0.18),
    ("Zona Oeste", 0.12),
    ("La Plata", 0.08),
    ("Mar del Plata", 0.06),
    ("Rosario", 0.08),
    ("Córdoba", 0.06),
]

DIA_SEMANA_ES = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
]


def _pick_weighted(rng: np.random.Generator, pairs: list[tuple[str, float]]) -> str:
    names, weights = zip(*pairs, strict=True)
    return str(rng.choice(names, p=np.array(weights) / np.sum(weights)))


def _edad_a_rango(edad: int) -> str:
    if edad < 2:
        return "0-1"
    if edad < 12:
        return "2-11"
    if edad < 18:
        return "12-17"
    if edad < 35:
        return "18-34"
    if edad < 55:
        return "35-54"
    if edad < 70:
        return "55-69"
    return "70+"


def _sample_demora_dias(rng: np.random.Generator) -> int:
    # Sesgo a pocos días; cola larga
    x = float(rng.gamma(shape=2.0, scale=4.0))
    return int(min(60, max(0, round(x))))


def _estado_turno_from_demora(rng: np.random.Generator, demora: int) -> str:
    p_asistido, p_cancel, p_ausente, p_reprog = 0.74, 0.11, 0.09, 0.06
    if demora > 14:
        p_asistido, p_cancel, p_ausente, p_reprog = 0.58, 0.17, 0.17, 0.08
    if demora > 30:
        p_asistido, p_cancel, p_ausente, p_reprog = 0.48, 0.20, 0.22, 0.10
    s = p_asistido + p_cancel + p_ausente + p_reprog
    p = np.array([p_asistido, p_cancel, p_ausente, p_reprog]) / s
    return str(rng.choice(["asistido", "cancelado", "ausente", "reprogramado"], p=p))


def _parse_dias_atencion(s: str) -> set[int]:
    """Map 'lun_mié_vie' -> {0,2,4}; 'lun_a_vie' -> 0..4; 'mar_jue' -> {1,3}."""
    s0 = s.lower().replace("á", "a").replace("é", "e")
    if "lun_a_vie" in s0 or "lunes_a_viernes" in s0:
        return {0, 1, 2, 3, 4}
    days: set[int] = set()
    for part in s0.replace("_", " ").split():
        if part.startswith("lun"):
            days.add(0)
        elif part.startswith("mar"):
            days.add(1)
        elif part.startswith("mie") or part.startswith("mi"):
            days.add(2)
        elif part.startswith("jue"):
            days.add(3)
        elif part.startswith("vie"):
            days.add(4)
        elif part.startswith("sab"):
            days.add(5)
        elif part.startswith("dom"):
            days.add(6)
    return days if days else {0, 1, 2, 3, 4}


def _sample_date_for_pro(
    rng: np.random.Generator,
    allowed_weekdays: set[int],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Timestamp:
    delta_days = int((end - start).days)
    for _ in range(500):
        off = int(rng.integers(0, delta_days + 1))
        d = start + pd.Timedelta(days=off)
        if d.weekday() in allowed_weekdays:
            return d.normalize()
    return start.normalize()


def build_patients(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    start_alta = pd.Timestamp("2019-01-01")
    end_alta = pd.Timestamp("2025-06-01")
    for pid in range(1, N_PATIENTS + 1):
        edad = int(rng.integers(1, 96))
        if rng.random() < 0.78:
            edad = int(rng.integers(18, 81))
        sexo = "F" if rng.random() < 0.54 else "M"
        cob = _pick_weighted(rng, COBERTURAS)
        loc = _pick_weighted(rng, LOCALIDADES)
        alta = _sample_date_for_pro(rng, {0, 1, 2, 3, 4, 5, 6}, start_alta, end_alta)
        rows.append(
            {
                "patient_id": pid,
                "sexo": sexo,
                "edad": edad,
                "rango_edad": _edad_a_rango(edad),
                "cobertura_medica": cob,
                "localidad": loc,
                "fecha_alta": alta.date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def build_professionals(rng: np.random.Generator) -> pd.DataFrame:
    # 4 Clínica médica, 3 Cardiología, 5 otras especialidades (total 12)
    specs: list[tuple[str, str, str, str]] = [
        ("Dra. Ana Martínez", "Clínica médica", "lun_mié_vie", "mañana"),
        ("Dr. Carlos Gómez", "Clínica médica", "mar_jue", "tarde"),
        ("Dra. Laura Fernández", "Clínica médica", "lun_a_vie", "mixto"),
        ("Dr. Pablo Ruiz", "Clínica médica", "lun_a_vie", "mañana"),
        ("Dr. Miguel Sánchez", "Cardiología", "lun_mié_vie", "mañana"),
        ("Dra. Verónica López", "Cardiología", "mar_jue", "mañana"),
        ("Dr. Diego Torres", "Cardiología", "lun_a_vie", "tarde"),
        ("Dra. Julia Castro", "Dermatología", "mar_jue", "tarde"),
        ("Dr. Martín Acosta", "Traumatología", "lun_a_vie", "mañana"),
        ("Dra. Carolina Vega", "Ginecología", "lun_mié_vie", "tarde"),
        ("Dr. Federico Morales", "Neurología", "mar_jue", "mañana"),
        ("Dra. Silvia Romero", "Pediatría", "lun_a_vie", "mixto"),
    ]
    assert len(specs) == N_PROFESSIONALS

    rows = []
    for i, (nombre, esp, dias, turno) in enumerate(specs, start=1):
        rows.append(
            {
                "professional_id": i,
                "nombre_profesional": nombre,
                "especialidad": esp,
                "antiguedad_anios": int(rng.integers(2, 26)),
                "dias_atencion": dias,
                "turno_habitual": turno,
            }
        )
    return pd.DataFrame(rows)


def build_appointments(
    rng: np.random.Generator,
    professionals: pd.DataFrame,
) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2024-12-31")

    spec_list = professionals["especialidad"].tolist()
    counts = professionals.groupby("especialidad").size()
    raw_w = []
    for s in spec_list:
        base = float(SPECIALTY_APPOINTMENT_WEIGHTS.get(str(s), 0.0))
        raw_w.append(base / int(counts[str(s)]))
    weights = np.array(raw_w, dtype=float)
    weights = weights / weights.sum()

    tipos = ["control", "primera_vez", "seguimiento", "urgencia"]
    tipo_w = np.array([0.42, 0.22, 0.30, 0.06])
    canales = ["web", "telefono", "presencial", "app"]
    canal_w = np.array([0.35, 0.28, 0.22, 0.15])

    rows = []
    pro_allowed: dict[int, set[int]] = {}
    for _, pr in professionals.iterrows():
        pid = int(pr["professional_id"])
        pro_allowed[pid] = _parse_dias_atencion(str(pr["dias_atencion"]))

    for aid in range(1, N_APPOINTMENTS + 1):
        pro_idx = int(rng.choice(len(professionals), p=weights))
        pr = professionals.iloc[pro_idx]
        professional_id = int(pr["professional_id"])
        especialidad = str(pr["especialidad"])
        allowed = pro_allowed[professional_id]
        fecha_ts = _sample_date_for_pro(rng, allowed, start, end)
        fecha = fecha_ts.date()
        mes = int(fecha.month)
        wd = int(fecha_ts.weekday())
        dia_semana = DIA_SEMANA_ES[wd]

        # Franja: más densidad mañana
        if rng.random() < 0.64:
            franja = "mañana"
        else:
            franja = "tarde"

        tipo_consulta = str(rng.choice(tipos, p=tipo_w / tipo_w.sum()))
        demora = _sample_demora_dias(rng)
        estado_turno = _estado_turno_from_demora(rng, demora)
        canal = str(rng.choice(canales, p=canal_w / canal_w.sum()))

        if tipo_consulta == "urgencia":
            dur = int(rng.choice([20, 30, 45]))
        elif tipo_consulta == "primera_vez":
            dur = int(rng.choice([30, 40, 45]))
        else:
            dur = int(rng.choice([15, 20, 30]))

        patient_id = int(rng.integers(1, N_PATIENTS + 1))

        rows.append(
            {
                "appointment_id": aid,
                "patient_id": patient_id,
                "professional_id": professional_id,
                "fecha_turno": fecha.isoformat(),
                "mes": mes,
                "dia_semana": dia_semana,
                "franja_horaria": franja,
                "especialidad": especialidad,
                "tipo_consulta": tipo_consulta,
                "estado_turno": estado_turno,
                "canal_reserva": canal,
                "demora_dias": demora,
                "duracion_estimada_min": dur,
            }
        )
    return pd.DataFrame(rows)


def _base_monto(especialidad: str, tipo: str, rng: np.random.Generator) -> float:
    base = {
        "Clínica médica": 5200.0,
        "Cardiología": 7800.0,
        "Dermatología": 6100.0,
        "Traumatología": 6900.0,
        "Ginecología": 7200.0,
        "Neurología": 8500.0,
        "Pediatría": 5800.0,
    }.get(especialidad, 6000.0)
    mult = {"primera_vez": 1.15, "urgencia": 1.25, "seguimiento": 0.95, "control": 1.0}.get(tipo, 1.0)
    noise = float(rng.normal(0, base * 0.06))
    return max(2500.0, base * mult + noise)


def build_billing(
    rng: np.random.Generator,
    appointments: pd.DataFrame,
    patients: pd.DataFrame,
) -> pd.DataFrame:
    patient_cob = patients.set_index("patient_id")["cobertura_medica"].to_dict()
    rows = []
    bid = 0
    for _, ap in appointments.iterrows():
        estado = str(ap["estado_turno"])
        if estado != "asistido":
            continue
        # Algunos asistidos sin facturación inmediata (pocos)
        if rng.random() < 0.04:
            continue
        bid += 1
        aid = int(ap["appointment_id"])
        pid = int(ap["patient_id"])
        esp = str(ap["especialidad"])
        tipo = str(ap["tipo_consulta"])
        monto = round(_base_monto(esp, tipo, rng), 2)

        cob_paciente = patient_cob.get(pid, "Particular")
        # Medio de pago según cobertura (heurística simple)
        if cob_paciente == "Particular":
            medio = str(rng.choice(["efectivo", "tarjeta", "transferencia"], p=[0.35, 0.45, 0.20]))
        elif cob_paciente in ("PAMI", "OSECAC"):
            medio = str(rng.choice(["tarjeta", "transferencia", "efectivo"], p=[0.25, 0.35, 0.40]))
        else:
            medio = str(rng.choice(["tarjeta", "transferencia", "efectivo"], p=[0.5, 0.35, 0.15]))

        if rng.random() < 0.12:
            estado_pago = "pendiente"
            fecha_pago = np.nan
        elif rng.random() < 0.05:
            estado_pago = "rechazado"
            fecha_pago = np.nan
        else:
            estado_pago = "pagado"
            fecha_turno = pd.Timestamp(str(ap["fecha_turno"]))
            lag = int(rng.integers(0, 8))
            fecha_pago = (fecha_turno + pd.Timedelta(days=lag)).date().isoformat()

        copago = round(float(rng.uniform(0, monto * 0.25)), 2)
        if rng.random() < 0.08:
            copago = np.nan
        if estado_pago != "pagado":
            if rng.random() < 0.5:
                copago = np.nan

        ingreso_neto = monto - (copago if pd.notna(copago) else 0.0)
        ingreso_neto = round(max(0.0, ingreso_neto), 2)

        # cobertura en facturación: a veces coincide con paciente; nulos controlados
        cobertura = cob_paciente
        if rng.random() < 0.06:
            cobertura = np.nan

        rows.append(
            {
                "billing_id": bid,
                "appointment_id": aid,
                "monto_consulta": monto,
                "medio_pago": medio,
                "estado_pago": estado_pago,
                "fecha_pago": fecha_pago,
                "cobertura": cobertura,
                "copago": copago,
                "ingreso_neto": ingreso_neto,
            }
        )
    return pd.DataFrame(rows)


def build_flat(
    appointments: pd.DataFrame,
    patients: pd.DataFrame,
    professionals: pd.DataFrame,
    billing: pd.DataFrame,
) -> pd.DataFrame:
    p = patients.copy()
    pro_cols = ["professional_id", "nombre_profesional", "antiguedad_anios", "dias_atencion", "turno_habitual"]
    pro_sub = professionals[pro_cols]
    flat = appointments.merge(p, on="patient_id", how="left")
    flat = flat.merge(pro_sub, on="professional_id", how="left")
    flat = flat.merge(billing, on="appointment_id", how="left")

    column_order = [
        "appointment_id",
        "patient_id",
        "professional_id",
        "fecha_turno",
        "mes",
        "dia_semana",
        "franja_horaria",
        "especialidad",
        "tipo_consulta",
        "estado_turno",
        "canal_reserva",
        "demora_dias",
        "duracion_estimada_min",
        "sexo",
        "edad",
        "rango_edad",
        "cobertura_medica",
        "localidad",
        "fecha_alta",
        "nombre_profesional",
        "antiguedad_anios",
        "dias_atencion",
        "turno_habitual",
        "billing_id",
        "monto_consulta",
        "medio_pago",
        "estado_pago",
        "fecha_pago",
        "cobertura",
        "copago",
        "ingreso_neto",
    ]
    flat = flat[column_order]
    if "billing_id" in flat.columns:
        flat["billing_id"] = flat["billing_id"].astype("Int64")
    for c in ("monto_consulta", "copago", "ingreso_neto"):
        if c in flat.columns:
            flat[c] = pd.to_numeric(flat[c], errors="coerce")
    return flat


def main() -> None:
    rng = np.random.default_rng(SEED)
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "legacy" / "data" / "sample" / "medical_clinic"
    out_dir.mkdir(parents=True, exist_ok=True)

    patients = build_patients(rng)
    professionals = build_professionals(rng)
    appointments = build_appointments(rng, professionals)
    billing = build_billing(rng, appointments, patients)
    flat = build_flat(appointments, patients, professionals, billing)

    patients.to_csv(out_dir / "patients.csv", index=False, encoding="utf-8")
    professionals.to_csv(out_dir / "professionals.csv", index=False, encoding="utf-8")
    appointments.to_csv(out_dir / "appointments.csv", index=False, encoding="utf-8")
    billing.to_csv(out_dir / "billing.csv", index=False, encoding="utf-8")
    flat.to_csv(out_dir / "medical_clinic_flat.csv", index=False, encoding="utf-8")

    print(f"Escrito en {out_dir}")
    print(f"  patients: {len(patients)}, professionals: {len(professionals)}")
    print(f"  appointments: {len(appointments)}, billing: {len(billing)}, flat: {len(flat)} rows")


if __name__ == "__main__":
    main()
