# Paradigm — Arquitectura final

**Fecha:** 2026-07-22  
**Síntesis ejecutiva:** arquitectura consolidada de Paradigm, alineada con el estado actual y con la arquitectura objetivo.

Paradigm es un laboratorio personal de inteligencia aplicada sobre datos sintéticos. Hoy funciona como una plataforma local, reproducible y de bajo costo para explorar datos, modelar riesgo, explicar hallazgos y apoyar decisiones con aprobación humana. No es un producto comercial ni multiusuario.

La arquitectura actual resumida es simple: Streamlit orquesta la UI, Python concentra la lógica, SQLite guarda el mart y los archivos sostienen CSV, reportes, modelos, evaluaciones e índices RAG locales. Las superficies visibles actuales son Executive Overview, Conciliación, No-Show ML, Forecasting, AI Conversational Insights, Governance & Improvement, Automation Lab y Paradigm Copilot. El punto de entrada principal es `streamlit_app.py`.

La base modular inicial ya existe y se separa en tres bloques:

- **Módulos funcionales actuales**: core analítico, analista conversacional y **Paradigm Copilot V1** (explicación/revisión de SQL, explicación de Python, análisis de errores y propuestas de corrección con revisión humana obligatoria; sin ejecutar SQL/Python, sin editar archivos, sin historial persistente).
- **Módulos estructurales actuales**: **Automation Lab** y **Governance & Improvement** como páginas de estructura y marco de trabajo, todavía sin lógica operativa persistente.
- **Capacidades futuras**: automatizaciones ejecutables, scheduler, tool calling, ejecución segura de código, historial persistente del Copilot, persistencia remota, colaboración multiusuario y agentes autónomos.

La arquitectura objetivo resumida organiza la plataforma por capacidades: Paradigm como núcleo, ClarusFlow para ingesta/calidad/transformación/gobierno de datos, LumenVox para lenguaje/feedback/clasificación/análisis textual, Paradigm Copilot como compañero contextual de SQL/Python/Data Science, Automation Lab para disparadores/acciones/aprobaciones/historial, y Governance & Improvement para riesgos, limitaciones, evaluaciones, decisiones y mejoras. Lo avanzado de esos módulos sigue siendo roadmap y no debe leerse como ya operativo.

El ecosistema actual es conceptual, no integrado por repositorios: ClarusFlow y LumenVox forman parte del relato de plataforma, mientras Paradigm consume artefactos locales y coordina análisis y decisión. No existe dependencia runtime entre repositorios.

Persistencia actual: SQLite local en `data/processed/paradigm_mart.db`, CSV y archivos en `data/synthetic/` y `reports/`, artefactos de experimento en `ml/experiments/` y `ml/figures/`, y un índice RAG local en `data/processed/rag_index/`. PostgreSQL o una base remota quedan como opción futura, no como requisito.

Principios: uso personal, modularidad, trazabilidad, aprobación humana, bajo costo y ejecución local cuando sea posible.

Core actual, objetivo y legacy se distinguen así: el core actual vive en `streamlit_app.py`, `app/`, `python/src/paradigm/`, `ml/`, `scripts/`, `bi/`, `sql/` y `tests/`; el core objetivo separa mejor capacidades por módulo; legacy incluye `legacy/app/main.py`, `app/conversational/legacy_bridge.py`, `generate_medical_clinic_data.py` y duplicaciones históricas de ML y UI.

Roadmap por fases: 1) ordenar y documentar la base actual; 2) separar mejor Copilot, Automation Lab y Governance & Improvement; 3) reforzar trazabilidad, aprobación y evaluación; 4) evaluar una base remota solo si aporta valor real.
