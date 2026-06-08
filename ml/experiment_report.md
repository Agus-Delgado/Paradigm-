# Reporte de experimento — No-Show ML (Paradigm v2)

Documento de portfolio sobre el experimento de **priorización** de no-shows. Los números concretos se regeneran con `make ml` y quedan en `ml/experiments/metrics.json`.

---

## 1. Por qué el AUC es bajo (~0.40–0.42)

En el hold-out temporal del mart sintético actual:

| Modelo | ROC-AUC (test) | Nota |
|--------|----------------|------|
| Logistic Regression | ~0.40 | Por debajo del azar |
| Random Forest | ~0.42 | Señal débil |

**Causas esperadas (no un bug de implementación):**

1. **Datos sintéticos** — el generador no modela drivers fuertes de no-show; las tasas históricas por paciente/proveedor son ruidosas y con pocos eventos.
2. **Muestra pequeña en test** — ~91 citas y ~11 no-shows en hold-out; las métricas de ranking son inestables.
3. **Objetivo del repo** — demostrar **metodología** (target, leakage, split temporal, explicabilidad, impacto operativo), no accuracy de producción.

El experimento se presenta como **ranking / priorización** (“¿a quién contacto primero?”), no como clasificador calibrado para decisión automática.

---

## 2. Prevención de leakage y split temporal

### Punto de decisión

Scoring inmediatamente **después de la reserva**: solo información conocible en `booking_ts` y calendario del turno.

### Features excluidas (leakage)

- Estado final de la cita, cancelación, facturación.
- Historial que incluya la cita actual (se usa `shift(1)` y fechas estrictamente anteriores).

Implementación: `python/src/paradigm/ml/features.py`.

### Split temporal

- Orden por `appointment_date` (no shuffle aleatorio).
- Train = fechas ≤ cutoff; test = fechas posteriores (~80/20 de fechas distintas).
- Cutoff de referencia en la última corrida: ver `temporal_cutoff_appointment_date` en `metrics.json`.

Esto simula despliegue: el modelo solo ve el pasado al entrenar y predice citas futuras.

---

## 3. Interpretación SHAP

Tras `make ml` se generan:

- `data/processed/shap_bundle.joblib` — valores SHAP del hold-out (Random Forest).
- `ml/figures/shap_summary_beeswarm.png` — summary plot global.

**Drivers típicos (mean |SHAP|):**

1. `provider_prior_appt_count` / `provider_prior_no_show_rate` — historial del profesional.
2. `lead_time_days` — anticipación de la reserva.
3. Features de calendario (`appointment_month`, `booking_hour`, `appointment_hour`, `appointment_dow`).

**Lectura honesta:** SHAP describe **asociaciones** en el modelo entrenado, no efectos causales. Con AUC bajo, las explicaciones locales deben leerse como “qué usó el modelo”, no como “qué causa el no-show en la realidad”.

Importancias tabulares también en `metrics.json` → `shap_importance_top` (o `feature_importances_top` como respaldo).

---

## 4. Simulación de impacto de negocio

Módulo: `python/src/paradigm/ml/business_impact.py`.

Dado un **top X%** de citas por score descendente en el hold-out:

| Métrica | Definición |
|---------|------------|
| Citas priorizadas | `ceil(n_test × X%)` |
| No-shows en el slice | positivos reales en ese top |
| Slots liberados est. | no-shows en slice × tasa de reasignación (default 100%) |
| Ingreso recuperado (ARS) | slots liberados × valor promedio por cita |

**Valor por cita:** promedio desde `fact_billing_line` (no VOID); fallback a `vw_revenue_bridge`; último recurso constante demo (`12_500 ARS`).

Resultados de referencia (top 10%) en `metrics.json` → `business_impact_top10pct`.

**Limitación:** estimación ilustrativa sobre datos sintéticos; no reemplaza un piloto operativo ni ROI auditado.

---

## 5. Reproducibilidad

```bash
make install      # pipeline + shap + matplotlib
make all          # synthetic → mart → quality → BI → validate → ml
make demo         # Streamlit (pestaña No-Show ML)
```

Artefactos clave (rutas en `paradigm.io.paths`):

| Artefacto | Ruta |
|-----------|------|
| Mart | `data/processed/paradigm_mart.db` |
| Modelos | `ml/experiments/no_show_*.joblib` |
| Métricas | `ml/experiments/metrics.json` |
| Bundle SHAP | `data/processed/shap_bundle.joblib` |
| Summary PNG | `ml/figures/shap_summary_beeswarm.png` |

---

## 6. Próximos pasos (fuera de alcance del repo)

- Datos reales con gobernanza y volumen suficiente.
- Calibración de probabilidades y umbrales por unidad de negocio.
- A/B de intervenciones (SMS, llamada) para estimar tasa real de recupero de slots.
- Monitoreo de drift y re-entrenamiento programado.
