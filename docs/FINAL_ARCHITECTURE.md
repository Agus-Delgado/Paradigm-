# Paradigm — Arquitectura final

**Fecha:** 2026-07-22
**Alcance:** estado técnico consolidado del laboratorio (sin cambiar UI ni modelos).
**Complementa:** [`architecture.md`](architecture.md) (mart/BI), [`PARADIGM_TARGET_ARCHITECTURE.md`](PARADIGM_TARGET_ARCHITECTURE.md) (objetivo), reportes de laboratorio en `docs/`.

---

## 1. Posicionamiento

Paradigm es un **laboratorio de inteligencia de decisiones** sobre operaciones ambulatorias **sintéticas**. La UI (Streamlit, BI, chat) **consume** artefactos; no es la fuente de verdad.

```text
Observe → Predict → Explain → Decide → Learn
```

| Capa | Pregunta | Artefactos típicos |
|------|----------|--------------------|
| **Observe** | ¿Qué pasó? ¿El mart es íntegro? | `data/synthetic/`, `paradigm_mart.db`, quality, KPIs, BI |
| **Predict** | ¿Qué riesgo / demanda esperar? | `paradigm.ml`, `paradigm.ml_v2`, forecasting, scores |
| **Explain** | ¿Por qué el score / el periodo? | SHAP, analista conversacional, eval gold |
| **Decide** | ¿A quién contactar bajo qué política? | `paradigm.prescriptive`, `decision_layer`, what-if UI |
| **Learn** | ¿Regresionó el laboratorio? | `ml/experiments/runs/`, CI, tests, drift |

No se afirma causalidad clínica ni se automatizan campañas reales.

---

## 2. Dos stacks (naming)

| Nombre | Qué es | Ruta activa |
|--------|--------|-------------|
| **Portfolio / mart** | Datos dimensionales + Live Demo | `data/synthetic/` → mart → `paradigm.ml` → Streamlit |
| **Lab v2** | Generador con señal controlable + uplift/Decide | `data/synthetic_v2/` → `paradigm.ml_v2` → uplift → `paradigm.prescriptive` |

“v2” en la **app Streamlit** = Live Demo sobre el mart. “v2” en **lab** = `synthetic_v2` / `ml_v2`. Son paralelos; Make/`make all` cubre el portfolio, no el lab completo.

---

## 3. Mapa del repositorio

```text
Paradigm/
├── app/                         # UI Streamlit + capa conversacional
│   ├── conversational/          # Observe/Explain/Decide (chat); sin cambios de UI en Decide
│   │   ├── decision_layer.py    # Decide headless (paradigm.prescriptive)
│   │   └── legacy_bridge.py     # LEGACY — puente a legacy/app/core
│   ├── config/, data.py, ui.py, …
│   └── ml_predict.py, forecasting.py
├── streamlit_app.py             # Entry Live Demo
├── python/src/paradigm/         # Core instalable (sin Streamlit)
│   ├── io/, quality/            # Observe
│   ├── ml/                      # Predict portfolio (mart)
│   ├── ml_v2/, synthetic_v2/    # Predict lab
│   ├── monitoring/              # Learn (segmentación/drift)
│   └── prescriptive/            # Decide headless
├── ml/
│   ├── experiments/             # Learn registry (API nueva + tracker legacy)
│   │   ├── runs/                # GENERADO — no versionar
│   │   ├── contract.py, runner.py, store.py, run_id.py
│   │   ├── tracker.py           # LEGACY flat tracker
│   │   └── metrics.json         # Snapshot portfolio (intencional)
│   ├── forecasting/             # Predict demanda
│   └── prescriptive/            # Decide UI what-if (Monte Carlo; distinto del engine)
├── scripts/                     # CLIs activos del portfolio + lab
├── legacy/                      # App v1 + samples + scripts aislados
│   ├── app/, data/sample/
│   └── scripts/                 # generate_medical_clinic, verify_dynamic_questions
├── data/
│   ├── synthetic/               # CSVs mart (versionados / regenerables)
│   ├── synthetic_v2/            # GENERADO lab — no versionar
│   └── processed/               # mart.db, shap, rag, jsonl — regenerables
├── sql/, bi/, reports/, docs/, tests/, assets/
├── requirements.txt             # core (CI)
├── requirements-dev.txt         # + pytest
├── requirements-llm.txt         # RAG/LLM opcional
└── requirements-app.txt         # Streamlit + plotly + llm
```

---

## 4. Rutas activas por capa

### Observe

| Acción | Entrypoint |
|--------|------------|
| Generar mart CSVs | `scripts/generate_paradigm_v2_synthetic.py` |
| Construir SQLite | `scripts/build_sqlite_mart.py` |
| Calidad | `scripts/run_data_quality.py` → `paradigm.quality` |
| KPIs | `scripts/validate_executive_kpis.py` |
| BI | `scripts/export_powerbi_source.py`, `export_tableau_source.py` |

### Predict

| Stack | Entrypoint | Paquete |
|-------|------------|---------|
| Portfolio no-show | `scripts/train_no_show.py` | `paradigm.ml` |
| Lab no-show | `scripts/train_no_show_v2.py` | `paradigm.ml_v2` |
| Lab uplift | `scripts/train_uplift_v2.py` | `paradigm.ml_v2.uplift_*` |
| Forecast | `scripts/train_forecast.py` | `ml.forecasting` |
| Lab synthetic | `scripts/generate_synthetic_v2.py` | `paradigm.synthetic_v2` |

### Explain

| Superficie | Módulo |
|------------|--------|
| SHAP / importances | `paradigm.ml.explain`, tab No-Show |
| Chat + RAG / heurística | `app.conversational.llm_service` |
| SQL / Data Explorer | `nl_to_sql`, `data_explorer` (UI) |
| Eval conversacional | `app.conversational.evaluation` |

### Decide

| Superficie | Módulo | Nota |
|------------|--------|------|
| Engine headless | `paradigm.prescriptive` + `scripts/run_prescriptive_engine.py` | Fuente de verdad Decide |
| Chat Decide | `app.conversational.decision_layer` | Sin cambio de UI; hook en `generate_insights` |
| What-if Streamlit | `ml.prescriptive` | Recommender + Monte Carlo en UI |

### Learn

| Superficie | Módulo |
|------------|--------|
| Runs estructurados | `ml.experiments` (`start_run` / `runs/<id>/`) |
| Drift / segmentos | `paradigm.monitoring` + `scripts/run_segmentation_drift.py` |
| CI | `.github/workflows/ci.yml` — imports core, pytest, mart, quality, KPIs |
| Tests | `tests/` (ver `tests/README.md`) |

---

## 5. Legacy e isolación

| Ítem | Estado |
|------|--------|
| `legacy/app` | App Streamlit v1 opcional |
| `legacy/scripts/*` | Generador flat + verify ad-hoc (fuera de Make/CI) |
| `app.conversational.legacy_bridge` | **Aún en camino crítico** del analista (profiling/findings) — marcar, no eliminar |
| `ml.experiments.tracker` | Flat tracker legacy; coexistente con `runs/` |
| `app.conversational.flow` | Helpers de wizard UI; acoplado a Streamlit |

No borrar `legacy/` mientras `legacy_bridge` importe `core.*`.

---

## 6. Artefactos: qué versionar

| Versionar | No versionar (gitignore) |
|-----------|--------------------------|
| `data/synthetic/*.csv` | `data/synthetic_v2/` |
| `ml/experiments/metrics.json` (baseline portfolio) | `ml/experiments/runs/` |
| Código under `ml/experiments/*.py` | `**/*.joblib`, predicciones CSV regenerables |
| `reports/quality_report.md`, gold eval (evidencia) | `data/processed/*.db`, `*.jsonl`, `rag_index/` |
| Docs / SQL / tests | Timestamped forecast snapshot folders |

---

## 7. Dependencias

| Archivo | Uso |
|---------|-----|
| `requirements.txt` | Core pipeline + ML (CI) |
| `requirements-dev.txt` | pytest |
| `requirements-llm.txt` | LangChain, FAISS, embeddings |
| `requirements-app.txt` | Streamlit + Plotly + llm |

Core **debe** importarse sin Streamlit (validado en CI).

---

## 8. Validación rápida

```bash
# Suite
pytest tests/ -v

# Portfolio (v1 ML sobre mart)
python scripts/build_sqlite_mart.py
python scripts/train_no_show.py

# Lab v2 (requiere synthetic_v2 generado)
python scripts/train_no_show_v2.py --dataset-id signal_moderate_seed42 --seed 42

# Imports core sin Streamlit
PYTHONPATH=python/src python -c "import paradigm.prescriptive, paradigm.ml, app.conversational.decision_layer"
```

Detalle de intents Decide: [`CONVERSATIONAL_DECISION_LAYER.md`](CONVERSATIONAL_DECISION_LAYER.md).
Contrato de experimentos: [`EXPERIMENT_STANDARD.md`](EXPERIMENT_STANDARD.md).
