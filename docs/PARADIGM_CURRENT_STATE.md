# Paradigm — Estado actual del repositorio

**Fecha de revisión:** 2026-07-22  
**Alcance:** inventario factual del estado actual.  
**Fuera de alcance:** arquitectura objetivo, refactors o capacidades futuras.

## 1. Propósito actual

Paradigm es hoy un laboratorio personal de analítica aplicada sobre datos sintéticos. Sirve para explorar, explicar, predecir y documentar decisiones; no es un producto comercial ni multiusuario.

## 2. Stack real y entrada principal

El stack real es Python + Streamlit + SQLite local. El punto de entrada principal es [streamlit_app.py](streamlit_app.py), que carga el mart SQLite y orquesta la UI desde `app/`.

## 3. Secciones visibles actuales

La navegación actual expone ocho secciones, más landing inicial y filtros laterales para vistas de negocio:

1. Executive Overview
2. Conciliación
3. No-Show ML
4. Forecasting
5. AI Conversational Insights
6. Governance & Improvement
7. Automation Lab
8. Paradigm Copilot

## 4. Módulos y capacidades realmente existentes

Existen bloques reales en `scripts/`, `app/`, `ml/`, `python/src/paradigm/`, `bi/`, `sql/` y `tests/`.

Capacidades actuales:

- mart SQLite local, calidad de datos, exports BI;
- ranking de no-show con SHAP, forecasting de demanda;
- analista conversacional con NL→SQL/RAG y evaluación;
- **Paradigm Copilot V1**: explicación de SQL, revisión de SQL, explicación de Python, análisis de errores y propuestas de corrección; siempre con revisión humana obligatoria, sin ejecutar SQL/Python, sin edición de archivos y sin historial persistente;
- **Automation Lab (estructural)**: página existente sin automatizaciones activas, sin scheduler, sin ejecución automática y sin persistencia propia;
- **Governance & Improvement (estructural)**: página existente con riesgos, limitaciones, backlog de mejoras y principios, sin persistencia ni seguimiento operativo.

La UI prescriptiva sigue viviendo dentro de No-Show ML.

## 5. Persistencia actual

- **SQLite**: mart local en `data/processed/paradigm_mart.db`.
- **CSV y archivos**: `data/synthetic/`, exports BI, reportes Markdown, joblibs, figuras y bundles SHAP.
- **Experimentos y reportes**: `ml/experiments/`, `reports/`, `ml/figures/`.
- **Índice RAG local**: `data/processed/rag_index/`.

## 6. Integración con ClarusFlow y LumenVox

La integración actual con ClarusFlow y LumenVox es conceptual y de ecosistema, no directa entre repositorios. Paradigm los referencia como parte del relato de plataforma, pero no hay acoplamiento runtime ni dependencia técnica externa.

## 7. Legacy y duplicaciones conocidas

Persisten duplicaciones y compatibilidades históricas: `legacy/app/main.py`, `app/conversational/legacy_bridge.py`, `generate_paradigm_v2_synthetic.py` y `generate_medical_clinic_data.py`, además de dos zonas de ML separadas (`python/src/paradigm/ml` y `ml/`).

## 8. Capacidades todavía no implementadas

Siguen siendo futuras:

- automatizaciones ejecutables;
- scheduler;
- tool calling;
- ejecución segura de código;
- historial persistente del Copilot;
- persistencia remota;
- colaboración multiusuario;
- agentes autónomos.

## 9. Próximos pasos inmediatos

1. Mantener el hilo centrado en la documentación factual del repo.
2. Reducir contradicciones entre README, docs y código visible.
3. Separar con claridad qué es actual, qué es legacy y qué queda para fases futuras.

## 10. Cierre

El estado actual es operativo para un laboratorio individual, con base local, ocho páginas visibles y una primera capa modular inicial ya expuesta (Copilot V1 funcional, Automation/Governance estructurales). Lo pendiente es transformar módulos estructurales en capacidades operativas sin confundir estado actual con roadmap.
