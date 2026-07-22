# Paradigm — Estándar de experimentos

**Fecha:** 2026-07-21
**Entrada:** [`PARADIGM_CURRENT_STATE.md`](PARADIGM_CURRENT_STATE.md), [`PARADIGM_TARGET_ARCHITECTURE.md`](PARADIGM_TARGET_ARCHITECTURE.md), `ml/README.md`, `ml/experiment_report.md`, `scripts/train_no_show.py`, `scripts/train_forecast.py`, `ml/experiments/tracker.py`, `ml/prescriptive/*`.
**Alcance:** contrato metodológico único para experimentos del laboratorio.
**Fuera de alcance:** implementación de código o nuevos archivos de soporte.

---

## 0. Propósito

Todo experimento en Paradigm —clasificación, regresión, forecasting, clustering, causalidad, simulación o políticas prescriptivas— debe poder auditarse con el mismo contrato de **18 campos**, la misma **plantilla**, la misma **convención de artefactos** y la misma **regla de promoción**.

El estándar alinea el ciclo del laboratorio:

```text
Observe → Predict → Explain → Decide → Learn
```

y obliga a **no mezclar** claims entre:

| Claim permitido | Qué mide | Qué no implica |
|-----------------|----------|----------------|
| **Rendimiento predictivo** | Error / ranking / calibración en hold-out o backtest | Causa ni ROI real |
| **Interpretación** | Qué usó el modelo (importances, SHAP, perfiles) | Efecto causal |
| **Causalidad** | Efecto de tratamiento bajo diseño explícito | Score predictivo ni SHAP |
| **Impacto simulado** | What-if bajo supuestos S (Monte Carlo, escenarios) | Evidencia empírica de uplift |
| **Decisión recomendada** | Política rankeada para revisión humana | Ejecución automática ni outcome clínico |

Referencia viva hoy: no-show (`ml/README.md`) documenta predictivo + interpretación; `business_impact` y `ml/prescriptive` documentan impacto simulado / decisión recomendada — **no** causalidad.

---

## 1. Tipos de experimento cubiertos

| Tipo | Definición operativa en Paradigm | Ejemplo actual o previsto |
|------|----------------------------------|---------------------------|
| **Clasificación** | Predicción de clase o score de ranking sobre unidad discreta | No-show ATTENDED vs NO_SHOW |
| **Regresión** | Predicción de cantidad continua en grano tabular | (No MVP; p. ej. lead time, revenue por cita) |
| **Forecasting** | Predicción de serie temporal hacia horizonte H | Demanda diaria (`train_forecast.py`) |
| **Clustering** | Segmentación no supervisada para diagnóstico | Mencionado en `ml/README` como next step; sin MVP |
| **Causalidad** | Estimación de efecto de intervención / exposición | **Ausente** en código; solo plantilla + gates |
| **Simulación** | Propagación de incertidumbre bajo supuestos | Monte Carlo `simulate_what_if` |
| **Políticas prescriptivas** | Mapeo evidencia → acción recomendada + trade-offs | `recommend_interventions` + perfiles |

Un run puede **encadenar** tipos (p. ej. clasificación → simulación → política) pero cada tipo debe tener su bloque de contrato o un `experiment_chain` que los enlace sin fusionar métricas.

---

## 2. Contrato único (18 campos)

Todo experimento completo debe responder estos campos. Si un campo no aplica, se marca `N/A` con justificación de una línea — no se omite en silencio.

### 2.1 Pregunta e hipótesis

- **Pregunta de negocio** (idealmente anclada a T1–T6 / Decide).
- **Hipótesis falsable** (qué resultado esperamos vs baseline).
- **Capa del lab:** Predict / Explain / Decide / Learn (Observe solo si el experimento es de calidad de datos).

### 2.2 Unidad de análisis

- Grano de la fila o del timestep (cita, día×especialidad, paciente, etc.).
- Universo de inclusión/exclusión (alineado a `metrics.md` cuando aplique).

### 2.3 Target o resultado

- Definición exacta del label / serie / outcome / utilidad simulada.
- Qué **no** es el target (anti-alcance).

### 2.4 Punto de decisión

- Momento en el que se usa el output (p. ej. post-booking, D−1, planificación semanal).
- Información legítimamente observable en ese instante.

### 2.5 Ventana temporal

- Rango de datos de entrenamiento / evaluación.
- Horizonte de predicción o de simulación.
- Zona horaria / anclaje de fechas (`appointment_date`, `billing_date`, etc.).

### 2.6 Variables disponibles y excluidas

- Lista o catálogo de features / drivers / supuestos.
- Variables **excluidas a propósito** (ética, leakage, fuera de alcance).

### 2.7 Riesgos de leakage

- Checklist de filtraciones temporales, de label, de agregados que incluyen el presente, de post-tratamiento en causalidad.
- Mitigaciones concretas (orden temporal, `shift`, cutoff).

### 2.8 Baseline

- Al menos un baseline trivial o interpretativo obligatorio:
  - clasificación: tasa positiva / ranking aleatorio / logística simple;
  - forecasting: `naive_last` o `seasonal_naive`;
  - clustering: un solo cluster o reglas de negocio;
  - causalidad: outcome medio sin ajuste / diferencia cruda (con disclaimer);
  - simulación/política: “no intervenir” o política actual documentada.

### 2.9 Split o estrategia de validación

| Tipo | Validación mínima esperada |
|------|----------------------------|
| Clasificación / regresión | Split **temporal** por fecha de evento (no shuffle i.i.d. por defecto) |
| Forecasting | Backtest expanding/rolling + hold-out de horizonte |
| Clustering | Estabilidad (seeds) + validez diagnóstica; sin “accuracy” engañosa |
| Causalidad | Diseño (RCT / cuasi-experimental) + checks de solapamiento / balance |
| Simulación | Seeds fijos + sensibilidad de supuestos |
| Políticas | Comparación contra baseline de política + stress de parámetros |

### 2.10 Métricas principales y secundarias

- **Principales:** deciden promover / mantener / descartar.
- **Secundarias:** diagnóstico (calibración, error por segmento, costo simulado).
- Toda métrica debe declarar si es **predictiva**, **interpretativa**, **causal**, **simulada** o de **política**.

### 2.11 Análisis de error

- Dónde falla (segmentos, folds, cuantiles).
- Errores costosos vs benignos (p. ej. falsos negativos de no-show en top-decile).
- Para forecast: residuos y peores folds del backtest.

### 2.12 Incertidumbre

- Intervalos, Brier/calibración, dispersión Monte Carlo, IC causales, o al menos **qualitative confidence** + tamaño muestral.
- En sintético: declarar alta incertidumbre por diseño.

### 2.13 Segmentos críticos

- Cortes operativos mínimos (especialidad, canal, proveedor, periodo).
- Métricas o conteos por segmento aunque el n sea bajo (con caveat).

### 2.14 Criterio de éxito

- Umbrales vs baseline (absolutos o relativos).
- En Paradigm sintético, el éxito puede ser **metodológico** (contrato completo + artefacto reproducible) aunque el AUC sea &lt; 0.5 — si así se declara explícitamente.

### 2.15 Impacto operativo

- Acción ilustrativa (priorizar, revisar, simular política).
- **Prohibido:** afirmar despliegue clínico o ROI real sin datos reales y diseño causal/simulación etiquetada.

### 2.16 Limitaciones

- Datos sintéticos, n pequeño, deps faltantes, ausencia de causalidad, supuestos de intervención, etc.

### 2.17 Artefactos obligatorios

Ver §4. Sin el set mínimo, el experimento no es “cerrado”.

### 2.18 Condiciones para promover, mantener o descartar

| Decisión | Condición (plantilla) |
|----------|------------------------|
| **Promover** | Contrato 18/18; baseline batida en métricas principales *o* éxito metodológico declarado; artefactos completos; sin leakage conocido; reporte firmado (commit + seed). |
| **Mantener** | Útil como referencia/demo; métricas débiles pero honestas; se re-ejecuta en CI/Learn como regresión de proceso. |
| **Descartar** | Leakage; métricas no reproducibles; claims causales sin diseño; deps no declaradas que impiden rerun; duplicado sin mejora vs baseline. |

“Promover” en este lab significa: **entrada al happy path documentado / demo / CI**, no producción clínica.

---

## 3. Diferenciación obligatoria de claims

Al reportar resultados, usar etiquetas explícitas en `metrics.json` / reporte:

```text
claim_namespace:
  predictive_performance: ...
  interpretation: ...
  causality: ...          # null si no aplica
  simulated_impact: ...
  recommended_decision: ...
```

Reglas:

1. **SHAP / feature importance** → solo `interpretation`.
2. **ROC-AUC, MAE, silhouette** → `predictive_performance` (o calidad de clustering).
3. **ATE / uplift** → solo `causality` con diseño citado.
4. **Slots liberados, revenue ARS del Monte Carlo / top-decile impact** → `simulated_impact` + lista de supuestos.
5. **Intervention key recomendada** → `recommended_decision`; nunca se ejecuta en repo.

Violación del estándar: mezclar estas secciones en un único número “de negocio” sin etiquetar.

---

## 4. Convención mínima de artefactos

### 4.1 Directorio de run

```text
ml/experiments/<UTC_YYYYMMDD_HHMMSS>_<slug>/
  config.json                 # hiperparámetros, seeds, paths relativos, tipo
  metrics.json                # métricas + claim_namespace
  predictions.parquet|csv     # scores / y_hat / clusters / escenarios
  figures/                    # PNG/SVG de error, SHAP, forecast, etc.
  model.joblib|pkl            # si hay modelo serializable (opcional en clustering puro)
  report.md                   # instancia de la plantilla §5
  metadata.json               # id, git_commit, timestamps, status, artifact map
```

Alineado con el espíritu de `ExperimentTracker` actual (`metadata.json`, métricas, model, figuras), endureciendo:

- **paths relativos al repo** (no `C:\...`);
- `config.json` separado (hoy a menudo embebido en `hyperparameters` de metadata);
- `predictions.*` explícitas (hoy no siempre versionadas en no-show);
- `report.md` por run (hoy existe `ml/experiment_report.md` genérico de portfolio).

### 4.2 Contenido mínimo por archivo

| Archivo | Debe incluir |
|---------|--------------|
| `config.json` | `experiment_type`, seed(s), data_revision (hash o fecha mart), decision_point, split spec, model name, feature list ref |
| `metrics.json` | principales/secundarias + `claim_namespace` + baseline metrics |
| `predictions.*` | id de unidad, y_true si existe, y_score/y_hat, fold/segment flags |
| `figures/` | ≥1 gráfico de error o explicación según tipo |
| `model.*` | pipeline reproducible **o** `model: null` justificado |
| `report.md` | plantilla §5 completa |
| `metadata.json` | `experiment_id`, `git_commit`, `started_at_utc`, `finished_at_utc`, `status`, mapa de artefactos |

### 4.3 Naming

- `slug`: `no_show_rf`, `demand_seasonal_naive_all`, `prescriptive_what_if`, …
- Un run = un `experiment_id`; cadenas se vinculan con `parent_experiment_id` en config.

---

## 5. Plantilla Markdown reutilizable

Copiar a `report.md` del run (o a `docs/experiments/<id>.md` si se archiva en docs).

```markdown
# Experimento — <título>

| Campo | Valor |
|-------|-------|
| experiment_id | |
| experiment_type | classification \| regression \| forecasting \| clustering \| causality \| simulation \| prescriptive_policy |
| lab_layer | Predict \| Explain \| Decide \| Learn |
| git_commit | |
| status | promote \| maintain \| discard \| running |
| parent_experiment_id | |

## 1. Pregunta e hipótesis
- Pregunta:
- Hipótesis:
- Anclaje (T1–T6 / Decide):

## 2. Unidad de análisis
- Grano:
- Universo (inclusión / exclusión):

## 3. Target o resultado
- Definición:
- Anti-alcance:

## 4. Punto de decisión
- Momento:
- Información observable:

## 5. Ventana temporal
- Train / fit:
- Eval / backtest:
- Horizonte:

## 6. Variables disponibles y excluidas
- Incluidas:
- Excluidas (motivo):

## 7. Riesgos de leakage
- Riesgos:
- Mitigaciones:

## 8. Baseline
- Nombre:
- Resultado:

## 9. Split / validación
- Estrategia:
- Parámetros (test_ratio, step, folds, seeds):

## 10. Métricas
### Predictivas
| Métrica | Rol (principal/secundaria) | Valor | Baseline |
|---------|----------------------------|-------|----------|
| | | | |

### Interpretación / causalidad / simulación / decisión
| Namespace | Métrica o hallazgo | Valor | Supuestos |
|-----------|--------------------|-------|-----------|
| interpretation | | | |
| causality | | | |
| simulated_impact | | | |
| recommended_decision | | | |

## 11. Análisis de error
-

## 12. Incertidumbre
-

## 13. Segmentos críticos
| Segmento | n | Métrica clave | Nota |
|----------|---|---------------|------|
| | | | |

## 14. Criterio de éxito
- Declarado:
- ¿Cumplido? sí / no / metodológico-only:

## 15. Impacto operativo (ilustrativo)
- Acción sugerida para revisión humana:
- Qué **no** se automatiza:

## 16. Limitaciones
-

## 17. Artefactos
| Archivo | Path relativo |
|---------|---------------|
| config | |
| metrics | |
| predictions | |
| figures | |
| model | |
| metadata | |

## 18. Decisión Learn
- **promote / maintain / discard**
- Justificación:
```

---

## 6. Requisitos por tipo (resumen normativo)

### 6.1 Clasificación

- Target binario/multiclase + universo.
- Baseline logística o rate.
- Métricas mínimas: ROC-AUC **o** PR-AUC según desbalance; Brier o calibración cualitativa; captura top-k/fracción si el uso es ranking (como no-show).
- Interpretación opcional pero recomendada (SHAP); nunca como causa.

### 6.2 Regresión

- Target continuo; métricas MAE/RMSE (+ MAPE solo si no hay ceros problemáticos).
- Residual plots obligatorios en `figures/`.
- Split temporal por defecto en datos operativos.

### 6.3 Forecasting

- Serie univariada/multivariada con frecuencia declarada.
- Baseline `naive_last` o `seasonal_naive` **siempre** en el mismo run o run hermano linkeado.
- Backtest + MAE/RMSE/SMAPE (como `train_forecast.py`).
- Figuras: history+future y actual vs predicted del backtest.

### 6.4 Clustering

- Objetivo diagnóstico (segmentos), no “accuracy”.
- Métricas: silhouette / DBI **y** lectura operativa de perfiles.
- Estabilidad en ≥2 seeds.
- Prohibido vender clusters como causalidad o política sin capa Decide aparte.

### 6.5 Causalidad

- Tratamiento, outcome, asignación / instrumento / discontinuidad / matching — diseño explícito.
- Chequeos de balance / solapamiento.
- Sin diseño: el experimento **no** puede usar este tipo; reclasificar a interpretación o simulación.
- Hoy: tipo reservado; promover solo si existe diseño reproducible.

### 6.6 Simulación

- Lista versionada de supuestos (`effectiveness`, `uptake`, costos, `iterations`, seed) — ver perfiles en `InterventionProfile`.
- Outputs: distribución de impacto (mean/p10/p90), no un único punto sin dispersión.
- Namespace obligatorio: `simulated_impact`.

### 6.7 Políticas prescriptivas

- Entradas: scores Predict y/o forecast + perfiles.
- Salida: tabla de recomendaciones + brief.
- Comparar vs política baseline (“no action” o umbral único).
- Namespace: `recommended_decision`; ejecución humana fuera de repo.

---

## 7. Mapeo a experimentos ya existentes

| Experimento actual | Tipo(s) | Cumplimiento aproximado del estándar | Gap principal |
|--------------------|---------|--------------------------------------|---------------|
| No-show RF/Logistic | Clasificación (+ interpretación + impacto simulado top-decile) | Alto en campos 1–10, 16 | Predictions no siempre versionadas; report genérico vs por-run; claims a veces juntos en un solo `metrics.json` |
| Demand forecast | Forecasting | Medio–alto | Default `exp_smoothing`/Prophet frágil sin deps; baseline naive no siempre en el mismo run |
| Prescriptive what-if | Simulación + política | Medio | Supuestos en código; falta `report.md` por run y criterio promote formal |
| Causal uplift de recordatorios | Causalidad | Nulo | No implementado — no claim |

---

## 8. Tabla de cierre

| Tipo de experimento | Validación mínima | Métricas obligatorias | Artefactos |
|---------------------|-------------------|----------------------|------------|
| **Clasificación** | Split temporal (o justificación explícita); baseline | ROC-AUC y/o PR-AUC; Brier (o nota de calibración); top-fraction capture si uso=ranking | `config`, `metrics`, `predictions`, `model`, ≥1 figura (curva o SHAP), `report`, `metadata` |
| **Regresión** | Split temporal; baseline media/naive | MAE, RMSE; residual diagnostics | `config`, `metrics`, `predictions`, `model`, residual figure, `report`, `metadata` |
| **Forecasting** | Expanding/rolling backtest + horizonte H; baseline naive/seasonal | MAE, RMSE, SMAPE (backtest) | `config`, `metrics`, `predictions` (future + backtest), `model`, 2 figuras (forecast + backtest), `report`, `metadata` |
| **Clustering** | Multi-seed estabilidad; revisión de perfiles | Silhouette (o equivalente) + descripción operativa de clusters | `config`, `metrics`, `predictions` (labels), figura de perfiles, `report`, `metadata` (`model` opcional) |
| **Causalidad** | Diseño causal documentado + balance/overlap | Efecto (ATE/ATT/…) + IC; placebo/refutation si aplica | `config` (diseño), `metrics`, `predictions`/weights, figuras de balance, `report`, `metadata` |
| **Simulación** | Seed fijo; sensibilidad ≥1 parámetro | Media y dispersión del outcome simulado (p10/p90 o σ) | `config` (supuestos), `metrics`, `predictions`/iterations, figura before/after, `report`, `metadata` |
| **Políticas prescriptivas** | Comparación vs política baseline; supuestos versionados | Cobertura, costo esperado, utilidad simulada neta; conteo por intervención | `config` (perfiles), `metrics`, `predictions` (recomendaciones), export brief (md/csv), `report`, `metadata` |

---

## 9. Relación con otros documentos

| Documento | Relación |
|-----------|----------|
| `PARADIGM_TARGET_ARCHITECTURE.md` | Este estándar es el contrato de **Predict / Explain / Decide / Learn** a nivel de run |
| `ml/README.md` | Instancia histórica del contrato para clasificación no-show |
| `ml/experiment_report.md` | Narrativa de portfolio; los runs futuros deben preferir `report.md` por `experiment_id` |
| `analytical_questions.md` | Preguntas tronco y checklist de explainability liviano |
| `metrics.md` | Definiciones de KPIs descriptivos — no sustituyen métricas de experimento |

---

*Estándar metodológico. No implementa cambios de código ni crea otros archivos.*
