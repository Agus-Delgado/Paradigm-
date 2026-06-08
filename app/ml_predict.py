"""Predicción de no-show: formulario, SHAP, impacto de negocio y recomendación."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from app.config import (
    COLOR_ACCENT,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    MODEL_FILES,
    RECOMMENDATIONS,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    TRAIN_COMMAND,
)
from app.data import HISTORICAL_NUMERIC, load_historical_defaults
from app.plots import (
    business_impact_chart,
    shap_force_bar_chart,
    shap_global_importance_chart,
    shap_local_waterfall_chart,
)
from paradigm.io.paths import (
    ML_EXPERIMENTS_DIR,
    SHAP_BUNDLE_PATH,
    SHAP_SUMMARY_PNG,
)
from paradigm.ml.business_impact import simulate_from_shap_bundle
from paradigm.ml.explain import compute_shap_values, mean_abs_importance
from paradigm.ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def _model_path(name: str) -> Path:
    return ML_EXPERIMENTS_DIR / MODEL_FILES[name]


@st.cache_resource(show_spinner="Cargando modelo ML…")
def load_model(model_file: str):
    return joblib.load(ML_EXPERIMENTS_DIR / model_file)


@st.cache_resource(show_spinner="Cargando artefactos SHAP…")
def load_shap_bundle():
    if not SHAP_BUNDLE_PATH.is_file():
        return None
    return joblib.load(SHAP_BUNDLE_PATH)


@st.cache_data(show_spinner=False)
def load_metrics_json() -> dict | None:
    path = ML_EXPERIMENTS_DIR / "metrics.json"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


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


def _appointment_display_id(appointment_id: object) -> str:
    """IDs del mart son strings con prefijo 'APT-' (ej. APT-00001), no enteros."""
    label = str(appointment_id).replace("APT-", "", 1).lstrip("0")
    return label or "0"


def _prepare_test_meta(meta: pd.DataFrame) -> pd.DataFrame:
    """Normaliza metadata del hold-out para UI (display_id legible en selectbox)."""
    out = meta.copy()
    # appointment_id: código de negocio 'APT-NNNNN', no PK numérica
    out["display_id"] = (
        out["appointment_id"].astype(str).str.replace("APT-", "", regex=False).str.lstrip("0")
    )
    out["display_id"] = out["display_id"].replace("", "0")
    return out.reset_index(drop=True)


def _explain_row(pipe, X: pd.DataFrame, model_name: str) -> tuple[list[float], float, list[str]]:
    """SHAP para una fila (formulario o hold-out)."""
    shap_matrix, expected_value, feature_names = compute_shap_values(pipe, X, model_name)
    return shap_matrix[0].tolist(), expected_value, feature_names


def _render_shap_local(
    feature_names: list[str],
    shap_row: list[float],
    expected_value: float,
    subtitle: str,
) -> None:
    st.caption(subtitle)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            shap_local_waterfall_chart(feature_names, shap_row, expected_value, title="Waterfall SHAP"),
            use_container_width=True,
        )
    with c2:
        st.plotly_chart(
            shap_force_bar_chart(feature_names, shap_row, title="Force plot (Plotly)"),
            use_container_width=True,
        )


def render_shap_section(pipe, model_name: str, metrics: dict | None) -> None:
    st.subheader("Explicabilidad del Modelo (SHAP)")
    st.caption(
        "Explicación global entrenada sobre Random Forest (hold-out temporal). "
        "Las contribuciones locales no implican causalidad."
    )

    bundle = load_shap_bundle()
    importance: list[dict] = []
    if metrics:
        rf_metrics = metrics.get("metrics", {}).get("random_forest", {})
        importance = rf_metrics.get("shap_importance_top") or rf_metrics.get("feature_importances_top", [])

    if bundle:
        global_imp = mean_abs_importance(bundle["shap_values"], bundle["feature_names"])
        st.plotly_chart(
            shap_global_importance_chart(global_imp, title="Importancia global — mean |SHAP| (hold-out)"),
            use_container_width=True,
        )
    elif importance:
        st.plotly_chart(
            shap_global_importance_chart(importance, title="Importancia global (proxy desde metrics.json)"),
            use_container_width=True,
        )

    if SHAP_SUMMARY_PNG.is_file():
        with st.expander("Summary plot (beeswarm) — generado en entrenamiento"):
            st.image(str(SHAP_SUMMARY_PNG), use_container_width=True)
    elif not bundle:
        st.info(f"Ejecutá `make ml` para generar SHAP. Comando: `{TRAIN_COMMAND}`")
        return

    meta = _prepare_test_meta(bundle["test_meta"])
    options: list[str] = []
    for pos in range(len(meta)):
        row = meta.iloc[pos]
        proba = float(row.get("predicted_proba", 0))
        options.append(
            f"#{row['display_id']} · {row['appointment_date']} · "
            f"Riesgo: {proba:.1%} · "
            f"{'NO_SHOW' if row['y_true'] else 'ATTENDED'}"
        )

    idx = st.selectbox(
        "Cita del hold-out (explicación local)",
        range(len(options)),
        format_func=lambda i: options[i],
        key="shap_appointment_select",
    )
    selected = meta.iloc[idx]
    shap_row = bundle["shap_values"][idx].tolist()
    _render_shap_local(
        bundle["feature_names"],
        shap_row,
        float(bundle["expected_value"]),
        f"Cita APT-{selected['display_id']} — contribuciones SHAP",
    )


def render_business_impact_section(db_path_str: str) -> None:
    st.subheader("Simulación de Impacto de Negocio")
    st.caption(
        "Estimación demo sobre el hold-out temporal. Asume que cada no-show evitado "
        "libera un slot reasignable al valor promedio por cita (ARS)."
    )

    bundle = load_shap_bundle()
    if not bundle:
        st.info(f"Requiere entrenamiento con SHAP. Ejecutá: `{TRAIN_COMMAND}`")
        return

    top_pct = st.slider(
        "Top X% de citas de mayor riesgo a priorizar",
        min_value=5,
        max_value=50,
        value=10,
        step=5,
        key="impact_top_pct",
    )
    top_fraction = top_pct / 100.0

    impact = simulate_from_shap_bundle(
        db_path=Path(db_path_str),
        bundle=bundle,
        top_fraction=top_fraction,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Citas priorizadas", f"{impact['appointments_prioritized']:,}")
    m2.metric("No-shows en el slice", f"{impact['no_shows_in_prioritized']:,}")
    m3.metric("Slots liberados est.", f"{impact['slots_liberated_est']:,.1f}")
    m4.metric(
        "Ingreso recuperado",
        f"${impact['revenue_recovered_ars']:,.0f} ARS",
        help=f"Promedio por cita: ${impact['avg_revenue_ars']:,.0f} ({impact['avg_revenue_source']})",
    )

    st.caption(
        f"Capture rate en top {top_pct}%: "
        f"{impact['capture_rate'] * 100:.1f}% de no-shows del hold-out · "
        f"Ingreso en riesgo baseline: ${impact['baseline_revenue_at_risk_ars']:,.0f} ARS"
    )

    comparison = impact["comparison_df"].copy()
    comparison.loc[
        comparison["scenario"].str.contains("Top"),
        "scenario",
    ] = f"Top {top_pct}% priorizado"

    st.plotly_chart(
        business_impact_chart(comparison, top_pct),
        use_container_width=True,
    )


def render_prediction_tab(
    tables: dict[str, pd.DataFrame],
    db_path_str: str,
    db_mtime: float,
) -> None:
    st.subheader("No-Show Prediction")
    st.caption(
        "Simulación de priorización con el modelo entrenado sobre datos sintéticos. "
        "No es un sistema de producción — ver `ml/README.md` y `ml/experiment_report.md`."
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
    metrics = load_metrics_json()

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

    predict_clicked = st.button("Calcular probabilidad de no-show", type="primary")
    if predict_clicked:
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

        st.session_state["last_prediction"] = {
            "X": X,
            "proba": proba,
            "model_name": model_name,
            "level": level,
        }

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

    last = st.session_state.get("last_prediction")
    if last and model_name == last.get("model_name"):
        if st.button("Explicar esta predicción", key="explain_last_prediction"):
            try:
                internal_name = "random_forest" if "Forest" in model_name else "logistic_regression_baseline"
                shap_row, expected_value, feature_names = _explain_row(
                    pipe, last["X"], internal_name
                )
                _render_shap_local(
                    feature_names,
                    shap_row,
                    expected_value,
                    f"Predicción simulada — riesgo {last['proba'] * 100:.1f}% ({last['level']})",
                )
            except Exception as exc:
                st.warning(f"No se pudo calcular SHAP para esta fila: {exc}")

    st.divider()
    render_shap_section(pipe, model_name, metrics)

    st.divider()
    render_business_impact_section(db_path_str)

    st.caption(
        f"Features esperadas: {len(CATEGORICAL_FEATURES)} categóricas + "
        f"{len(NUMERIC_FEATURES)} numéricas · ROC-AUC ~0.42 en hold-out sintético."
    )
