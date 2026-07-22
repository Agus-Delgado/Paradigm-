# Paradigm — Estado actual del repositorio

**Fecha de revisión:** 2026-07-21
**Alcance:** inventario y diagnóstico del código y documentación existentes.
**Fuera de alcance:** propuesta de arquitectura nueva, refactors o mejoras implementadas.

---

## 1. Arquitectura real actual

Paradigm es un portfolio de **analytics engineering + data science** sobre operaciones ambulatorias sintéticas. No hay API HTTP propia (FastAPI/Flask); el consumo interactivo es **Streamlit**. El núcleo analítico es un **mart SQLite dimensional**.

### Capas implementadas

```text
                    ┌─────────────────────────────────────────┐
                    │  scripts/  (pipeline CLI reproducible)  │
                    └───────────────────┬─────────────────────┘
                                        │
  data/synthetic/*.csv  ──►  data/processed/paradigm_mart.db  ──►  sql/views/*
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          ▼                             ▼                             ▼
   bi/{powerbi,tableau}/          python/src/paradigm/              ml/
   source_csv + DAX/docs          quality + ml (no-show)     forecasting +
                                                              prescriptive +
                                                              experiments/
          │                             │                             │
          └─────────────────────────────┼─────────────────────────────┘
                                        ▼
                         streamlit_app.py  ←  app/  (v2.1.0)
                              │
                              ├─ Executive Overview / Conciliación
                              ├─ No-Show ML (+ prescriptive UI)
                              ├─ Forecasting
                              └─ AI Conversational Insights
                                        │
                              legacy/app/core  (vía legacy_bridge)
```

### Runtime y empaquetado

| Pieza | Realidad |
|-------|----------|
| Lenguaje | Python 3.10+ (badge README); **CI y Docker fijan 3.11** |
| Dependencias | Solo `pip` + `requirements*.txt` (mínimos `>=`, sin lockfile) |
| Paquete librería | `python/src/paradigm` vía `PYTHONPATH` (no instalado como package editable) |
| UI principal | `streamlit_app.py` + paquete `app/` (`APP_VERSION = "2.1.0"`) |
| Contenedor | `Dockerfile` + `docker-compose.yml` (servicio `app`; perfil `init` para generar mart/ML) |
| Orquestación local | `Makefile` (`all`, `build-all`, `demo`, targets atómicos) |

### Diagrama conceptual en docs vs código

`docs/architecture.md` describe el flujo **sintético → mart → quality → PBI/Tableau/ML no-show**. Ese núcleo sigue vigente, pero el código ya incorpora además:

- Streamlit v2 como superficie principal de demo;
- forecasting (`ml/forecasting/` + tab UI);
- prescriptive / what-if (`ml/prescriptive/` + sección en No-Show ML);
- analista conversacional híbrido + evaluación gold (`app/conversational/`).

Esas capas **no** aparecen en el diagrama de despliegue de `docs/architecture.md`.

---

## 2. Módulos y responsabilidades

### Entrada y pipeline (`scripts/`)

| Script | Responsabilidad |
|--------|-----------------|
| `generate_paradigm_v2_synthetic.py` | Genera 9 dims + 2 facts en `data/synthetic/` (SEED/N_APPOINTMENTS) |
| `generate_medical_clinic_data.py` | Generador flat para `legacy/data/sample/` (v1) |
| `build_sqlite_mart.py` | DDL + carga ordenada + vistas → `data/processed/paradigm_mart.db` |
| `run_data_quality.py` | Ejecuta 14 checks → `reports/quality_report.md` |
| `export_powerbi_source.py` / `export_tableau_source.py` | Export CSV dual-lens |
| `validate_executive_kpis.py` | Validación numérica de KPIs ejecutivos |
| `train_no_show.py` | Entrena logistic + random forest + SHAP |
| `train_forecast.py` | Entrena forecast de demanda + backtest + experiment tracker |
| `run_evaluation_test.py` | Eval gold conversacional → `reports/evaluation_gold_report.json` |
| `verify_dynamic_questions.py` | Chequeo ad-hoc de preguntas dinámicas (no cableado a Make/CI) |

### Librería (`python/src/paradigm/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `io/paths.py` | Rutas canónicas (DB, experimentos, SHAP) |
| `quality/checks.py` | `ALL_CHECKS` — 14 validaciones sobre el mart |
| `quality/runner.py` / `report.py` | Orquestación y reporte Markdown |
| `ml/dataset.py` / `features.py` | Dataset y features de no-show |
| `ml/train.py` / `evaluate.py` / `explain.py` | Entrenamiento, métricas, SHAP |
| `ml/business_impact.py` | Bloque de impacto de negocio (priorización) |

### Demo Streamlit (`app/` + `streamlit_app.py`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `streamlit_app.py` | Entry, landing gate, sidebar de 5 páginas |
| `app/data.py` | Carga mart, KPIs, filtros, contexto de dataset analyst |
| `app/ui.py` | Landing, chrome, filtros, regeneración |
| `app/plots.py` | Gráficos Plotly (ejecutivo, SHAP, forecast, prescriptive) |
| `app/ml_predict.py` | Tab No-Show + sección prescriptiva |
| `app/forecasting.py` | Tab Forecasting (+ subprocess de train) |
| `app/export_report.py` | Helpers de export Markdown |
| `app/config/theme.py` | Tema, versión, constantes de modelos |
| `app/config/llm_config.py` | Settings LLM/RAG desde `.env` |
| `app/conversational/*` | Workspace conversacional (wizard, NL→SQL, RAG, explorers, eval) |
| `app/conversational/legacy_bridge.py` | Importa `legacy/app/core/*` en runtime |

### ML de producto (`ml/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `ml/forecasting/` | Modelos (naive, seasonal_naive, prophet*, exp_smoothing*), trainer, métricas |
| `ml/prescriptive/` | Recomendación de intervenciones + simulación Monte Carlo + export |
| `ml/experiments/` | Tracker, `metrics.json` no-show, corridas de forecast versionadas |
| `ml/README.md` / `experiment_report.md` | Metodología y límites del experimento no-show |

\*Prophet y Holt-Winters dependen de paquetes **no declarados** en `requirements*.txt` (ver §7).

### BI (`bi/`)

| Ruta | Responsabilidad |
|------|-----------------|
| `bi/powerbi/source_csv/` + `dax/` + `BUILD_INSTRUCTIONS.md` | Lente ejecutiva (CSV + DAX; `.pbix` no versionado) |
| `bi/tableau/source_csv/` + README | Lente diagnóstica (CSV; `.twbx` no versionado) |

### SQL (`sql/`)

| Ruta | Responsabilidad |
|------|-----------------|
| `sql/ddl/01_create_tables.sql` | Esquema dimensional |
| `sql/views/*.sql` (5) | Vistas KPI / appointment / revenue |
| `sql/samples/*.sql` (5) | Consultas de ejemplo (también corpus RAG) |

### Legacy (`legacy/`)

App Streamlit v1 + `core/` (schema, profiling, findings, ingestion, AI analytics). **No está muerto**: v2 lo usa vía `legacy_bridge`. App opcional: `streamlit run legacy/app/main.py`.

### Tests (`tests/`)

| Archivo | Alcance |
|---------|---------|
| `test_evaluation.py` | Métricas eval + evaluator + leaderboard |
| `test_llm_integration.py` | Seguridad, fallbacks, rate limit (mock) |
| `test_notebook_parser.py` / `test_notebook_analyzer.py` | Parsers de notebooks (sin notebooks commiteados) |

---

## 3. Flujo de datos de extremo a extremo

### Pipeline canónico (`make all`)

1. **Generación** — `generate_paradigm_v2_synthetic.py`
   - Escribe: `data/synthetic/dim_*.csv` (9) + `fact_appointment.csv` + `fact_billing_line.csv`
   - Parámetros documentados: `SEED=42`, ~520 citas, rango ~2024-01–2025-02.

2. **Mart** — `build_sqlite_mart.py`
   - Lee: CSVs + `sql/ddl/01_create_tables.sql` + `sql/views/*.sql`
   - Escribe: `data/processed/paradigm_mart.db` (gitignored).

3. **Calidad** — `run_data_quality.py`
   - Lee: mart
   - Escribe: `reports/quality_report.md` (14 checks; 1 warn esperado: attended without billing).

4. **BI** — export Power BI / Tableau
   - Escribe: `bi/powerbi/source_csv/*`, `bi/tableau/source_csv/*` (+ `KpiByProvider` en Tableau).

5. **Validación KPI** — `validate_executive_kpis.py` (stdout / assert numérico).

6. **ML no-show** — `train_no_show.py`
   - Escribe: `ml/experiments/*.joblib`, `metrics.json`, `data/processed/shap_bundle.joblib`, figuras SHAP.

### Extensiones (`make build-all` = `all` + extras)

7. **Forecast** — `train_forecast.py` → `ml/experiments/<id>/forecast_*`
8. **Eval gold** — `run_evaluation_test.py` → `reports/evaluation_gold_report.json`
9. **Test** — `unittest tests/test_evaluation.py`

### Consumo Streamlit

| Página | Lecturas principales |
|--------|----------------------|
| Executive / Conciliación | Mart vía `app.data.load_mart_tables` |
| No-Show ML | Mart + joblibs + SHAP bundle; opcional forecast para presión de demanda; export a `reports/prescriptive/` |
| Forecasting | Mart + experimentos forecast; puede relanzar train |
| AI Conversational | Dataset demo/sintético/upload (no solo mart); opcional LLM/RAG → `data/processed/rag_index/`, `llm_interactions.jsonl` |

### Modelo dimensional real

**9 dimensiones + 2 hechos** (confirmado por `LOAD_ORDER` y archivos en `data/synthetic/`):

`dim_date`, `dim_specialty`, `dim_coverage`, `dim_appointment_status`, `dim_booking_channel`, `dim_billing_status`, `dim_cancellation_reason`, `dim_patient`, `dim_provider`, `fact_appointment`, `fact_billing_line`.

---

## 4. Capacidades: BI, ML, forecasting, IA conversacional y simulación

### 4.1 BI

| Aspecto | Estado |
|---------|--------|
| Exports CSV desde mart | **Implementado** y cableado a Make |
| Medidas DAX + instrucciones PBI | **Presentes** en repo |
| Workbooks `.pbix` / `.twbx` | **No versionados** (requieren Desktop) |
| Evidencia visual | Screenshot `assets/dashboards/powerbi_executive.png` |
| Dual-lens (ejecutivo vs diagnóstico) | **Intencional**; CSVs casi duplicados por diseño de rol |

### 4.2 ML no-show

| Aspecto | Estado |
|---------|--------|
| Algoritmos | LogisticRegression (baseline) + RandomForestClassifier |
| Split | Temporal por `appointment_date` (~20% hold-out) |
| Métricas | ROC-AUC, AP, Brier, accuracy, top-decile capture |
| Explicabilidad | SHAP global/local + beeswarm |
| UI | Formulario, hold-out picker, impacto de negocio |
| Desempeño en artefactos | AUC ~0.40–0.42 en `ml/experiments/metrics.json` — **demo metodológica**, no poder predictivo fuerte (documentado en `ml/README.md` / `experiment_report.md`) |

### 4.3 Forecasting

| Aspecto | Estado |
|---------|--------|
| Código | `ml/forecasting/` + `scripts/train_forecast.py` + tab UI |
| Modelos en código | `naive_last`, `seasonal_naive`, `prophet`, `exp_smoothing` |
| Default CLI | `--model exp_smoothing`, horizon 45 |
| Experimento commiteado | `seasonal_naive`, horizon 30, backtest MAE/RMSE/SMAPE |
| Deps Prophet / statsmodels | **Ausentes** de `requirements*.txt` — modelos avanzados fallan sin install manual |
| Make `all` | **No** entrena forecast; sí `build-all` / `train-forecast` |

### 4.4 IA conversacional

| Aspecto | Estado |
|---------|--------|
| Wizard + análisis determinístico | **Real** (sin LLM) |
| NL→SQL | Híbrido: heurística + LLM opcional con validación SELECT/WITH |
| RAG | FAISS sobre `docs/data_dictionary.md`, `docs/metrics.md`, `sql/samples/*.sql` |
| Proveedores | ollama (default), groq, openai, grok, `disabled` |
| Fallbacks | Heurísticos cuando LLM no disponible / rate-limited |
| Workspace UI | 4 superficies: Análisis Guiado, SQL Explorer, Data Explorer, **Evaluation** |
| Gold eval | `data/eval_gold/conversational_eval_gold.json` + UI + script |
| Acoplamiento legacy | `legacy_bridge` importa profiling/schema/findings de v1 |

### 4.5 Simulación / prescriptive

| Aspecto | Estado |
|---------|--------|
| Recomendador | Rule-based (`recommend_interventions`, perfiles de intervención) |
| Simulación | Monte Carlo `simulate_what_if` (iteraciones, slots, revenue, costo) |
| UI | Dentro de **No-Show ML** (`render_prescriptive_section`), no página sidebar propia |
| Export | CSV/MD/ZIP → `reports/prescriptive/` (carpeta vacía hasta export) |
| Naturaleza | What-if / priorización operativa; **no** automatiza acciones clínicas |

---

## 5. Módulos duplicados, aislados, legacy o incompletos

### Duplicados / paralelos

| Ítem | Evidencia |
|------|-----------|
| Streamlit v2 vs v1 | `app/` + `streamlit_app.py` vs `legacy/app/main.py` |
| Dos generadores sintéticos | `generate_paradigm_v2_synthetic.py` vs `generate_medical_clinic_data.py` |
| Dos ubicaciones de lógica ML | `python/src/paradigm/ml/` (no-show) vs top-level `ml/` (forecast + prescriptive + experimentos) |
| Plots / analysis | `app/plots.py` vs `app/conversational/plots.py`; análisis tipado en conversational vs `legacy/.../ai_analytics` |
| CSVs BI | Export casi espejo PBI/Tableau (duplicación de rol, no accidental) |
| Screenshots | `assets/screenshots/` (usado por README) vs `assets/walkthrough/` (README de walkthrough desalineado) |

### Legacy acoplado (no aislado)

`app/conversational/legacy_bridge.py` inserta `legacy/app` en `sys.path` e importa `core.schema`, `core.profiling`, `core.findings`, `core.ingestion`, etc. Eliminar `legacy/` rompería partes del flujo conversacional v2.

### Aislados / poco cableados

| Ítem | Evidencia |
|------|-----------|
| `scripts/verify_dynamic_questions.py` | Fuera de Makefile y CI |
| `tests/test_notebook_*` | Sin notebooks en `python/notebooks/` (solo `.gitkeep`) |
| `tests/test_llm_integration.py` | No corre en CI ni en `make test-evaluation` |
| Carpetas placeholder | `data/raw/`, `ml/features/`, `python/notebooks/`, `assets/diagrams/`, `assets/bi/`, `reports/prescriptive/` (vacías o solo `.gitkeep`) |

### Incompletos respecto a lo anunciado

| Ítem | Evidencia |
|------|-----------|
| Forecast “Prophet-class” listo out-of-the-box | Código sí; deps no |
| Docker “LLM-ready” | `Dockerfile` copia solo `requirements.txt` + `requirements-app.txt` antes del `pip install`; `requirements-app.txt` hace `-r requirements-llm.txt` **antes** de `COPY . .` → install LLM puede fallar en build |
| Evaluación continua en CI | Roadmap README; **no** implementado |
| Workbooks BI versionados | Explicitamente no; OK si se lee la letra chica |

---

## 6. Diferencias entre README, documentación y código

| Claim | Fuente | Realidad en código |
|-------|--------|-------------------|
| **“11 dims + 2 facts”** | README Key Results; `docs/flow.mmd` | **9 dims + 2 facts** (`LOAD_ORDER`, `data/synthetic/`, `docs/architecture.md` y `sql/README.md` sí listan 9) |
| Tabla Live Demo: Overview / Conciliación / No-Show / AI | README § Live Demo | App tiene también **Forecasting**; AI tiene pestaña **Evaluation** |
| Workspace conversacional “3 pestañas” | `docs/conversational_insights_flow.md` | Código: **4** (`TAB_OPTIONS` incluye Evaluation) |
| Arquitectura de consumo: PBI + Tableau + ML | `docs/architecture.md` diagrama | Omite Streamlit, forecasting, prescriptive, eval framework |
| Badge “Streamlit Live Demo” | README | Solo local/Docker; **sin** URL hospedada |
| “tests automáticos” / evaluación en pipeline extendido | README Fases / `make build-all` | Solo `test_evaluation.py` en Make; CI no corre tests |
| Roadmap: “Evaluación continua … en CI” | README | Aspiracional; CI actual = mart + quality + KPI validate |
| Forecasting con Prophet / Holt-Winters | README Features table / CLI help | Implementado con imports opcionales; **no** en requirements |
| Python 3.10+ | Badge README | CI/Docker **3.11** (compatible, no idéntico) |
| Walkthrough paths en assets | `assets/walkthrough/README.md` | README principal usa `assets/screenshots/` |
| `v2.1` | README | Alineado con `APP_VERSION = "2.1.0"` |
| 14 quality checks | README / docs | **Correcto** (`len(ALL_CHECKS) == 14`) |
| Datos 100% sintéticos | Disclaimer | **Correcto** |

---

## 7. Dependencias, tests, CI y reproducibilidad

### Dependencias

| Archivo | Contenido |
|---------|-----------|
| `requirements.txt` | pandas, numpy, openpyxl, sklearn, joblib, shap, matplotlib, nbformat |
| `requirements-llm.txt` | langchain*, faiss-cpu, sentence-transformers, dotenv |
| `requirements-app.txt` | `-r` ambos + streamlit + plotly |

**Problemas:**

- Sin lockfile (`pip freeze` / poetry / uv) → builds no bit-reproducibles.
- `prophet` y `statsmodels` usados por forecasting **no** están declarados.
- Versiones mínimas `>=` permiten drift entre entornos.
- `nbformat` en requirements core sin notebooks versionados.
- Dockerfile: orden de COPY vs `-r requirements-llm.txt` fragiliza imagen completa.

### Tests

- Framework: `unittest` únicamente.
- Make: `test-evaluation` → solo `tests/test_evaluation.py`.
- Sin `pytest.ini`, `tox`, coverage gate, ni suite unificada.
- Tests LLM y notebooks existen pero quedan fuera del camino feliz de Make/CI.

### CI (`.github/workflows/ci.yml`)

- Trigger: **push a `main`** únicamente (no PRs).
- Pasos: checkout → Python 3.11 → `pip install -r requirements.txt` → build mart → quality → validate KPIs.
- **No ejecuta:** regeneración sintética, exports BI, train ML/forecast, eval-gold, unittest, Streamlit, LLM.

### Reproducibilidad

| Factor | Observación |
|--------|-------------|
| SEED sintético | Documentado; regenerable |
| Artefactos ML | Muchos `.joblib` gitignored; `metrics.json` y un run forecast sí versionados |
| Paths absolutos Windows | `metrics.json` y metadata de forecast guardan `C:\Proyectos\Paradigm\...` → frágil en otros OS/máquinas |
| Mart DB | Gitignored; debe reconstruirse |
| LLM | Depende de Ollama local o API keys; modo `disabled` mantiene flujo determinístico |
| Make en Windows | README asume GNU Make; en PowerShell puro se usan scripts Python equivalentes |

---

## 8. Riesgos técnicos prioritarios

1. **Forecast “completo” no reproducible out-of-the-box** — default `exp_smoothing` / Prophet requieren deps no listadas; el camino documentado en UI puede fallar en un clone limpio.

2. **Build Docker de la app LLM frágil** — `requirements-app.txt` referencia `requirements-llm.txt` antes de que el archivo esté en la imagen.

3. **CI demasiado estrecho vs narrativa Fases 1–4** — no protege ML, forecast, eval conversacional ni tests; regresiones en esas capas pueden llegar a `main` sin señal.

4. **Acoplamiento legacy en el camino crítico conversacional** — `legacy_bridge` + `sys.path` hace que v2 dependa de un árbol “legacy” no empaquetado.

5. **ML no-show con señal débil** — AUC &lt; 0.5 en artefactos; riesgo de sobreinterpretación en demos si no se enfatiza el disclaimer metodológico.

6. **Documentación desalineada (dims, tabs, arquitectura)** — genera expectativas falsas (“11 dims”, “3 pestañas”, arquitectura sin Streamlit/forecast).

7. **Sin pin/lock de dependencias** — shap / langchain / streamlit pueden romper el entorno con upgrades silenciosos.

8. **Paths absolutos en metadata de experimentos** — reduce portabilidad de artefactos entre máquinas.

9. **Superficie de tests incompleta** — parsers de notebooks y LLM integration no están en el gate; `verify_dynamic_questions` huérfano.

10. **Dualidad `paradigm.ml` vs `ml/`** — dos homes mentales para ML; aumenta costo de mantenimiento y riesgo de imports inconsistentes (`PYTHONPATH` vs `sys.path.insert` al root).

---

## 9. Tabla resumen

| Área | Estado | Evidencia | Problema | Prioridad |
|------|--------|-----------|----------|-----------|
| Mart dimensional + SQL views | Operativo | `build_sqlite_mart.py`, 9+2 CSVs, 5 views | README/flow.mmd dicen “11 dims” | Media (docs) |
| Quality (14 checks) | Operativo | `ALL_CHECKS`, CI + Make | — | Baja |
| Exports BI CSV + DAX | Operativo | `bi/*/source_csv`, `executive_measures.dax` | Sin `.pbix`/`.twbx` versionados (esperado) | Baja |
| Streamlit Executive / Conciliación | Operativo | `streamlit_app.py` páginas | — | Baja |
| ML no-show + SHAP | Operativo (demo) | `paradigm.ml`, `metrics.json`, tab UI | AUC ~0.40–0.42; priorización débil | Alta (expectativa) |
| Forecasting | Parcial | `ml/forecasting/`, tab, experimento `seasonal_naive` | `prophet`/`statsmodels` no en requirements; default `exp_smoothing` frágil | Alta |
| Prescriptive / Monte Carlo | Operativo | `ml/prescriptive/*`, UI en No-Show ML | Carpeta export vacía hasta uso; no página propia | Media |
| IA conversacional híbrida | Operativo | `app/conversational/*`, `.env.example` | Acoplado a legacy; LLM opcional | Media |
| Evaluation framework | Parcial | gold JSON, UI Evaluation, `test_evaluation.py` | Docs dicen 3 tabs; no en CI | Media |
| Legacy v1 | Acoplado | `legacy_bridge`, `legacy/README.md` | Dependencia estructural disfrazada de “opcional” | Alta |
| Dependencias / lock | Débil | solo `requirements*.txt` con `>=` | Sin pin; forecast deps faltantes | Alta |
| Docker | Parcial | `Dockerfile`, compose | COPY order vs `requirements-llm.txt` | Alta |
| CI | Estrecho | `.github/workflows/ci.yml` | No ML/forecast/tests/eval; solo push `main` | Alta |
| Tests | Fragmentados | 4 archivos unittest | Make/CI cubren subset mínimo | Media |
| Reproducibilidad experimentos | Parcial | tracker + metadata | Paths absolutos Windows en JSON | Media |
| Docs arquitectura | Desactualizada | `docs/architecture.md` vs código v2.1 | Omite Streamlit/forecast/prescriptive/eval | Media |
| Placeholders / huérfanos | Presentes | dirs vacíos, `verify_dynamic_questions.py` | Ruido y falsa sensación de completitud | Baja |

---

*Documento generado por revisión estática del repositorio. No incluye propuesta de arquitectura futura ni cambios de implementación.*
