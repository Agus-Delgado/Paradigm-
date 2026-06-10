"""Generación de datasets sintéticos con patrones analizables para demos."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

SyntheticDomain = Literal["healthcare", "finance", "operations"]

_DOMAIN_LABELS: dict[SyntheticDomain, str] = {
    "healthcare": "Sintético — consultorio médico",
    "finance": "Sintético — finanzas",
    "operations": "Sintético — operaciones",
}


def synthetic_source_label(domain: SyntheticDomain) -> str:
    return _DOMAIN_LABELS[domain]


def generate_synthetic_dataset(
    domain: SyntheticDomain,
    *,
    n_rows: int = 420,
    seed: int = 42,
) -> pd.DataFrame:
    """DataFrame con outliers, segmentos problemáticos y correlaciones detectables."""
    rng = np.random.default_rng(seed)
    if domain == "healthcare":
        return _generate_healthcare(rng, n_rows)
    if domain == "finance":
        return _generate_finance(rng, n_rows)
    return _generate_operations(rng, n_rows)


def _generate_healthcare(rng: np.random.Generator, n: int) -> pd.DataFrame:
    especialidades = ["Clínica", "Pediatría", "Cardiología", "Traumatología", "Dermatología"]
    medios = ["Obra social", "Prepaga", "Particular"]
    canales = ["Teléfono", "Web", "App", "Presencial"]
    estados_base = ["asistió", "ausente", "cancelado"]

    rows: list[dict] = []
    start = pd.Timestamp("2024-01-08")
    for i in range(n):
        esp = rng.choice(especialidades)
        canal = rng.choice(canales, p=[0.15, 0.35, 0.35, 0.15])
        medio = rng.choice(medios)

        p_ausente = 0.08
        if esp == "Cardiología":
            p_ausente = 0.28
        elif esp == "Pediatría":
            p_ausente = 0.12
        if canal == "Teléfono":
            p_ausente += 0.10
        if canal == "App":
            p_ausente -= 0.04

        p_ausente = min(max(p_ausente, 0.06), 0.35)
        weights = np.array([0.62, p_ausente, 0.28], dtype=float)
        weights /= weights.sum()
        estado = rng.choice(estados_base, p=weights)
        ingreso = float(rng.uniform(2800, 9200))
        if estado == "ausente":
            ingreso = 0.0
        elif esp == "Cardiología":
            ingreso *= 1.35
        if medio == "Particular":
            ingreso *= 1.15

        fecha = start + pd.Timedelta(days=int(rng.integers(0, 380)))
        rows.append(
            {
                "fecha_turno": fecha.date(),
                "paciente_id": f"P{rng.integers(1000, 9999):04d}",
                "especialidad": esp,
                "estado_turno": estado,
                "ingreso_neto": round(ingreso, 2),
                "medio_pago": medio,
                "cobertura_medica": medio,
                "canal_reserva": canal,
            }
        )
    return pd.DataFrame(rows)


def _generate_finance(rng: np.random.Generator, n: int) -> pd.DataFrame:
    centros = ["HQ", "Sucursal Norte", "Sucursal Sur", "Planta Logística"]
    cuentas = ["Marketing", "IT", "Operaciones", "RRHH", "Ventas"]
    periodos = pd.date_range("2024-01-01", periods=12, freq="MS")

    rows: list[dict] = []
    for _ in range(n):
        centro = rng.choice(centros)
        cuenta = rng.choice(cuentas)
        periodo = rng.choice(periodos)

        presupuesto = float(rng.uniform(50_000, 250_000))
        real = presupuesto * float(rng.uniform(0.85, 1.12))

        if centro == "Planta Logística" and cuenta == "Operaciones":
            real = presupuesto * float(rng.uniform(1.18, 1.45))
        if cuenta == "Marketing" and rng.random() < 0.08:
            real = presupuesto * float(rng.uniform(1.55, 1.85))

        variacion_pct = (real - presupuesto) / presupuesto * 100.0
        rows.append(
            {
                "periodo": pd.Timestamp(periodo).date(),
                "centro_costo": centro,
                "cuenta": cuenta,
                "presupuesto": round(presupuesto, 2),
                "real": round(real, 2),
                "variacion_pct": round(variacion_pct, 2),
                "moneda": "ARS",
            }
        )
    return pd.DataFrame(rows)


def _generate_operations(rng: np.random.Generator, n: int) -> pd.DataFrame:
    plantas = ["Planta A", "Planta B", "Planta C"]
    lineas = ["Ensamble", "Empaque", "Control calidad"]
    turnos = ["Mañana", "Tarde", "Noche"]

    rows: list[dict] = []
    start = pd.Timestamp("2024-02-01")
    for i in range(n):
        planta = rng.choice(plantas)
        linea = rng.choice(lineas)
        turno = rng.choice(turnos)

        unidades = int(rng.integers(80, 220))
        defectos = int(rng.poisson(2))
        ciclo = float(rng.uniform(12, 28))

        if planta == "Planta B":
            defectos = int(rng.poisson(8))
            if linea == "Ensamble":
                defectos = int(rng.poisson(12))
        if turno == "Noche":
            ciclo += float(rng.uniform(4, 9))
            defectos += int(rng.poisson(3))

        tasa_defecto = defectos / max(unidades, 1) * 100.0
        fecha = start + pd.Timedelta(days=int(rng.integers(0, 200)))
        rows.append(
            {
                "fecha": fecha.date(),
                "planta": planta,
                "linea": linea,
                "turno": turno,
                "orden_id": f"ORD-{i + 1000:05d}",
                "unidades": unidades,
                "defectos": defectos,
                "tasa_defecto_pct": round(tasa_defecto, 2),
                "tiempo_ciclo_min": round(ciclo, 1),
            }
        )
    return pd.DataFrame(rows)
