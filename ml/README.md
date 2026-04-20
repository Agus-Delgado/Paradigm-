# Machine Learning — Paradigm v2

## Encuadre: capa predictiva complementaria

Este módulo es la **capa predictiva** del proyecto de **inteligencia operativa aplicada**: estima **riesgo de no-show** en el punto de decisión documentado abajo. No reemplaza el análisis descriptivo ni el diagnóstico por cortes en BI; no es un servicio productivo ni una caja negra desconectada del negocio. Usa el **mismo mart** que Tableau y Power BI y se interpreta con las **definiciones de métricas** y las **limitaciones** del dataset sintético.

**Estado:** **implementado (MVP)** — modelo de **riesgo de no-show** a nivel cita, alineado al diccionario de métricas y al mart SQLite.

**Fuentes de verdad:** [`docs/metric_definitions.md`](../docs/metric_definitions.md), mart [`data/processed/paradigm_mart.db`](../data/processed/) vía [`scripts/build_sqlite_mart.py`](../scripts/build_sqlite_mart.py).

### Conexión con decisión operativa

El score apoya decisiones como:

- **Priorización de recordatorios** o contacto previo al turno cuando el riesgo predicho es alto (las políticas concretas quedan fuera del repo).
- **Revisión de grupos de mayor riesgo** agregado (p. ej. para focalizar análisis o campañas piloto en un entorno real).
- **Monitoreo preventivo** combinado con cortes en BI: el modelo sugiere *dónde* conviene mirar con más atención, no automatiza acciones.

La **explicabilidad** básica viene de las **importancias** del modelo y de la lectura honesta de `metrics.json`; no se presentan como causalidad.

---

## 1. Problema

Estimar la **probabilidad de no-show** en el momento de la **reserva**, para priorizar contactos o campañas de recordatorio (capa operativa; decisiones finas siguen siendo de negocio).

---

## 2. Variable objetivo (target)

- **Definición:** `target_no_show = 1` si la cita termina en **NO_SHOW**, `0` si **ATTENDED**.
- **Universo de filas:** solo citas con estado **ATTENDED** o **NO_SHOW** (mismo universo que el denominador del no-show rate en [`docs/metric_definitions.md`](../docs/metric_definitions.md): las **canceladas** no son parte de esta etiqueta).
- **Qué no es este modelo:** predicción de cancelación (otra etiqueta y otra ventana temporal).

---

## 3. Punto de decisión y leakage

| Momento | Qué significa |
|---------|----------------|
| **Punto de decisión (scoring)** | Inmediatamente **después de reservar**: se asume disponible todo lo observado en **`booking_ts` / `booking_date`** y el **calendario del turno** elegido (fecha/hora programada). |
| **Incluido (sin leakage)** | Canal, especialidad, cobertura, proveedor, paciente (banda etaria, sexo), anticipación **lead time** (turno − reserva), día/hora del turno y hora aproximada de reserva, **historial previo** del paciente y del proveedor en citas **anteriores** en el tiempo. |
| **Excluido (leakage)** | Estado final distinto de lo ya comprometido en el universo del modelo, **cancelación** y motivos, **cualquier facturación** o línea de cargo, agregados que incluyan la cita actual en el “pasado”, o información posterior al día del turno. |

Los features históricos usan solo citas con **fecha de turno estrictamente anterior** a la cita actual (orden por `appointment_date`, `appointment_start`, `appointment_id` dentro de paciente y de proveedor).

---

## 4. Dataset y features

**Construcción:** lectura desde SQLite (`fact_appointment` + `dim_appointment_status` + `dim_patient`) en [`paradigm/ml/dataset.py`](../python/src/paradigm/ml/dataset.py); ingeniería en [`paradigm/ml/features.py`](../python/src/paradigm/ml/features.py).

| Tipo | Features (MVP) |
|------|----------------|
| **Al reservar + calendario del turno** | `lead_time_days`, `appointment_hour`, `appointment_dow`, `appointment_month`, `booking_hour`; categorías `provider_id`, `specialty_id`, `booking_channel_id`, `coverage_id`, `age_band`, `sex`. |
| **Históricas (sin leakage)** | Conteos y tasas previas por **paciente** y por **proveedor:** `patient_prior_appt_count`, `patient_prior_no_show_count`, `patient_prior_no_show_rate`, `provider_prior_*` análogos. |
| **No usadas** | Estado de la cita, cancelación, facturación, IDs sensibles de paciente como “score” clínico (solo features tabulares del mart). |

---

## 5. Split temporal y evaluación

- **Split:** por **fecha del turno** `appointment_date` (no aleatorio por fila). Train = fechas **≤ corte**; test = fechas **posteriores** al corte. El corte se elige para dejar ~`1 - test_ratio` de las **fechas distintas** en entrenamiento (`test_ratio` por defecto `0.2` en [`train.py`](../python/src/paradigm/ml/train.py)).
- **Métricas de ranking:** ROC-AUC, average precision (PR-AUC), Brier (probabilidades).
- **Utilidad operativa:** **tasa de captura** de no-shows reales en el **top 10 %** de riesgo predicho en test (`top_decile` en `metrics.json`): cuántos de los no-shows caen en ese decil si se prioriza por score descendente.

---

## 6. Modelos

| Modelo | Rol |
|--------|-----|
| **Regresión logística** (`lbfgs`, `class_weight=balanced`) | Baseline lineal, interpretable. |
| **Random Forest** (`n_estimators=120`, `max_depth=10`, `class_weight=balanced`) | Modelo principal con **importancias de feature** exportadas en `metrics.json`. |

Sin búsqueda de hiperparámetros agresiva; objetivo = portfolio defendible y reproducible.

---

## 7. Interpretación

- Las **importancias** del bosque indican qué columnas (tras one-hot) más pesan; no son efectos causales.
- Métricas malas o AUC por debajo de 0.5 en el conjunto de test **son posibles** con datos **sintéticos** y muestras chicas: el valor del entregable es la **metodología** (punto de decisión, leakage, split temporal, métricas de negocio), no el récord predictivo.

### Plantilla de explicabilidad liviana

Para narrar el modelo en portfolio o entrevista, usar el checklist tabular en [`docs/analytical_questions.md`](../docs/analytical_questions.md) (sección 4, *Plantilla de explicabilidad liviana*): **señal**, **universo**, **punto de decisión**, **evidencia técnica** (`metrics.json`), **importancias** (sin confundir con causalidad), **riesgos de uso** y **tipo de acción** sugerida (priorización, no automatización en el repo).

---

## 8. Limitaciones del dataset sintético

- Patrones de no-show pueden ser **débiles o no realistas**; no conviene extrapolar conclusiones clínicas ni comerciales.
- Tamaño modesto → varianza alta en AUC/PR en el tramo de test.
- **Honestidad:** si `metrics.json` muestra desempeño pobre, tratarlo como **documentación de riesgo**, no como fallo de implementación.

---

## 9. Cómo correr el pipeline

Desde la **raíz del repositorio** (mismo entorno que el resto del proyecto; instalar dependencias: `pip install -r requirements.txt`):

```bash
python scripts/build_sqlite_mart.py
python scripts/train_no_show.py
```

**Salida:**

| Ruta | Contenido |
|------|------------|
| `ml/experiments/no_show_logistic.joblib` | Pipeline baseline entrenado |
| `ml/experiments/no_show_random_forest.joblib` | Pipeline Random Forest |
| `ml/experiments/metrics.json` | Fechas de train/test, métricas, importancias, captura top decil |

**Carga en Python (inferencia exploratoria):**

```python
import joblib
from pathlib import Path

pipe = joblib.load(Path("ml/experiments/no_show_random_forest.joblib"))
# X igual estructura que en entrenamiento (ver paradigm.ml.features)
# proba = pipe.predict_proba(X)[:, 1]
```

---

## 10. Estructura de código

| Ruta | Descripción |
|------|-------------|
| [`python/src/paradigm/ml/dataset.py`](../python/src/paradigm/ml/dataset.py) | Carga citas elegibles y target |
| [`python/src/paradigm/ml/features.py`](../python/src/paradigm/ml/features.py) | Historial + calendario; listas de columnas |
| [`python/src/paradigm/ml/evaluate.py`](../python/src/paradigm/ml/evaluate.py) | Métricas y captura top fracción |
| [`python/src/paradigm/ml/train.py`](../python/src/paradigm/ml/train.py) | Split temporal, entrenamiento, artefactos |
| [`scripts/train_no_show.py`](../scripts/train_no_show.py) | Punto de entrada reproducible |

No hay notebooks obligatorios; el flujo es script + paquete importable.

---

## 11. Próximos pasos (sin implementar en el repo aún)

Posibles extensiones futuras — **solo como línea de evolución**, no como compromiso de alcance: modelado explícito de **cancelación**, **segmentación** tipo clustering sobre comportamiento, u otras técnicas alineadas al mismo mart y a definiciones de negocio. El MVP actual se centra en **no-show** como caso predictivo documentado.
