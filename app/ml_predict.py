"""Predicción de no-show: formulario, carga de modelo y recomendación."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from app.config import (
    MODEL_FILES,
    RECOMMENDATIONS,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    TRAIN_COMMAND,
    COLOR_ACCENT,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
)
from app.data import HISTORICAL_NUMERIC, load_historical_defaults
from paradigm.io.paths import ML_EXPERIMENTS_DIR
from paradigm.ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def _model_path(name: str) -> Path:
    return ML_EXPERIMENTS_DIR / MODEL_FILES[name]


@st.cache_resource(show_spinner="Cargando modelo ML…")
def load_model(model_file: str):
    path = ML_EXPERIMENTS_DIR / model_file
    return joblib.load(path)


def get_recommendation(proba: float) -> tuple[str, str]:
    if proba >= THRESHOLD_HIGH:
        return "Alto", RECOMMENDATIONS["high"]
    if proba >= THRESHOLD_MEDIUM:
        return "Medio", RECOMMENDATIONS["medium"]
    return "Bajo", RECOMMENDATIONS["low"]


def build_feature_row(
    provider_id: int,
    specialty_id: int,
    booking_channel_id: int,
    coverage_id: int,
    age_band: str,
    sex: str,
    appointment_dt: datetime,
    booking_dt: datetime,
    historical: dict[str, float],
) -> pd.DataFrame:
    """Arma una fila con las 17 features esperadas por el pipeline sklearn."""
    lead_time = max((appointment_dt.date() - booking_dt.date()).days, 0)
    row = {
        "provider_id": provider_id,
        "specialty_id": specialty_id,
        "booking_channel_id": booking_channel_id,
        "coverage_id": coverage_id,
        "age_band": age_band,
        "sex": sex,
        "lead_time_days": lead_time,
        "appointment_hour": appointment_dt.hour,
        "appointment_dow": appointment_dt.weekday(),
        "appointment_month": appointment_dt.month,
        "booking_hour": booking_dt.hour,
    }
    for col in HISTORICAL_NUMERIC:
        row[col] = historical[col]
    return pd.DataFrame([row])


def render_prediction_tab(
    tables: dict[str, pd.DataFrame],
    db_path_str: str,
    db_mtime: float,
) -> None:
    st.subheader("No-Show Prediction")
    st.caption(
        "Simulación de priorización con el modelo entrenado sobre datos sintéticos. "
        "No es un sistema de producción — ver `ml/README.md`."
    )

    model_name = st.selectbox("Modelo", list(MODEL_FILES.keys()), index=0)
    model_file = MODEL_FILES[model_name]
    path = _model_path(model_name)

    if not path.is_file():
        st.warning("No se encontró el modelo entrenado.")
        st.code(TRAIN_COMMAND, language="bash")
        st.info("Requiere mart SQLite construido previamente.")
        return

    pipe = load_model(model_file)
    hist_defaults = load_historical_defaults(db_path_str, db_mtime)

    col1, col2 = st.columns(2)
    with col1:
        specialty_map = dict(
            zip(tables["specialties"]["specialty_name"], tables["specialties"]["specialty_id"])
        )
        specialty = st.selectbox("Especialidad", list(specialty_map.keys()))
        provider_map = dict(
            zip(tables["providers"]["provider_label"], tables["providers"]["provider_id"])
        )
        provider = st.selectbox("Profesional", list(provider_map.keys()))
        channel_map = {
            f"{r.channel_name} ({r.channel_code})": r.booking_channel_id
            for r in tables["channels"].itertuples()
        }
        channel = st.selectbox("Canal de reserva", list(channel_map.keys()))
        coverage_map = dict(
            zip(tables["coverages"]["coverage_name"], tables["coverages"]["coverage_id"])
        )
        coverage = st.selectbox("Cobertura", list(coverage_map.keys()))

    with col2:
        age_bands = sorted(tables["patients_meta"]["age_band"].unique())
        age_band = st.selectbox("Rango de edad", age_bands)
        sex = st.selectbox("Sexo", sorted(tables["patients_meta"]["sex"].unique()))
        appt_date = st.date_input("Fecha del turno", value=date.today())
        appt_time = st.time_input("Hora del turno", value=time(10, 0))
        book_date = st.date_input("Fecha de reserva", value=date.today())
        book_time = st.time_input("Hora de reserva", value=time(14, 0))

    with st.expander("Historial (opcional) — defaults = promedios del dataset"):
        st.caption(
            "Valores precargados desde el mart (citas ATTENDED + NO_SHOW). "
            "Ajustá solo si querés simular un perfil distinto."
        )
        historical: dict[str, float] = {}
        hcols = st.columns(2)
        for i, col_name in enumerate(HISTORICAL_NUMERIC):
            default = hist_defaults[col_name]
            with hcols[i % 2]:
                if col_name.endswith("_rate"):
                    historical[col_name] = st.number_input(
                        col_name,
                        min_value=0.0,
                        max_value=1.0,
                        value=round(default, 4),
                        step=0.01,
                        format="%.4f",
                    )
                else:
                    historical[col_name] = float(
                        st.number_input(
                            col_name,
                            min_value=0.0,
                            value=round(default, 2),
                            step=0.5,
                        )
                    )

    if st.button("Calcular probabilidad de no-show", type="primary"):
        appointment_dt = datetime.combine(appt_date, appt_time)
        booking_dt = datetime.combine(book_date, book_time)
        X = build_feature_row(
            provider_id=int(provider_map[provider]),
            specialty_id=int(specialty_map[specialty]),
            booking_channel_id=int(channel_map[channel]),
            coverage_id=int(coverage_map[coverage]),
            age_band=age_band,
            sex=sex,
            appointment_dt=appointment_dt,
            booking_dt=booking_dt,
            historical=historical,
        )

        proba = float(pipe.predict_proba(X)[0, 1])
        level, recommendation = get_recommendation(proba)
        color = COLOR_ACCENT if level == "Alto" else (COLOR_PRIMARY if level == "Medio" else COLOR_SUCCESS)

        m1, m2, m3 = st.columns(3)
        m1.metric("Probabilidad no-show", f"{proba * 100:.1f}%")
        m2.metric("Nivel de riesgo", level)
        m3.metric("Demora (días)", max((appt_date - book_date).days, 0))

        st.markdown(
            f"""
            <div style="border-left:4px solid {color};padding:0.75rem 1rem;
            background:rgba(13,148,136,0.08);border-radius:8px;margin-top:0.5rem;">
            <strong>Recomendación:</strong> {recommendation}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Vector de features enviado al modelo"):
            st.dataframe(X[CATEGORICAL_FEATURES + NUMERIC_FEATURES], use_container_width=True)

    st.markdown("---")
    st.caption(
        f"Features esperadas: {len(CATEGORICAL_FEATURES)} categóricas + "
        f"{len(NUMERIC_FEATURES)} numéricas · ROC-AUC ~0.42 en hold-out sintético."
    )
