# Paradigm — Estado actual del repositorio

**Fecha de revisión:** 2026-07-23  
**Alcance:** inventario factual tras el cierre de la migración visual mineral.  
**Fuera de alcance:** arquitectura objetivo, refactors de datos/ML o capacidades futuras.

## 1. Propósito actual

Paradigm es un laboratorio personal de observación, interpretación y decisión sobre datos sintéticos. Lenguaje visual: **mineral** (Home del prototipo aprobado extendido a shell y módulos Assistant/System). No es un producto comercial ni multiusuario.

## 2. Stack real y entrada principal

Python + Streamlit + SQLite local. Entrada: [streamlit_app.py](streamlit_app.py). Tokens en `assets/css/custom.css` (`--pd-*` mineral). Espejo parcial en `app/config/theme.py` y `.streamlit/config.toml` (puede atrasarse respecto al CSS).

## 3. Navegación (4 espacios → 8 vistas)

| Espacio (UI) | Space key | Vistas | Ids |
|--------------|-----------|--------|-----|
| Home | `Home` | composición mineral | `overview` |
| Work | `Workspaces` | Data & Quality, No-Show, Forecasting | `data_quality`, `no_show`, `forecasting` |
| Assistant | `Assistant` | Paradigm Assistant, Copilot | `conversational`, `copilot` |
| System | `System` | Automation Lab, Governance | `automations`, `governance` |

**Chrome actual**

- Topbar global: marca `P` + Home / Work / Assistant / System.
- Sidebar secundaria: dataset, vistas del espacio, filtros (overview + data_quality), recientes (máx. 3 sesión), mantenimiento.
- Page header mineral en páginas internas (no Home).

Claves: `paradigm_active_space`, `paradigm_active_view`, `paradigm_pending_task`, `paradigm_recent_tasks`.

## 4. Capas visuales actuales

### Home mineral
Marca en topbar; núcleo PARADIGM + CTA; secuencia cognitiva; launcher 7 destinos; Main Signal / Evidence / Next Action; charts Plotly. Sin fondo scoped por `:has()`.

### Assistant
Secuencia `Route → Dataset → Understand → Decide`; router determinista tipográfico; landing/wizard sin branding duplicado; chat/SQL/Data Explorer con overrides minerales. Lógica RAG/NL→SQL intacta.

### Copilot
Intake mineral + respuesta `Input → Analysis → Issues → Proposal → Risk`. Contrato/servicio sin cambios.

### Automation / Governance
Pipelines `.pd-auto-*` / `.pd-gov-*` (HTML compacto). Structural: sin scheduler, sin ejecución, sin persistencia propia.

### Data & Quality
Secuencia `.pd-process-rail` + métricas compactas. Cálculos sin cambio.

## 5. Persistencia actual

- SQLite: `data/processed/paradigm_mart.db`
- CSV/artefactos: `data/synthetic/`, BI, reportes, joblibs, SHAP
- Experimentos: `ml/experiments/`
- RAG local: `data/processed/rag_index/`

## 6. Integración con ClarusFlow y LumenVox

Conceptual / ecosistema. Sin acoplamiento runtime.

## 7. Legacy y limpieza visual

- Helpers huérfanos retirados de `app/ui.py` (automation/governance legacy generators, aliases Neural Canvas no referenciados).
- Aliases CSS `--cyan*` / `--bg-*` conservados solo por landing y clases residuales.
- CSS nuevo sin uso (`.pd-route-*`, `.pd-governance-*` de generadores viejos) retirado o sustituido por `.pd-assistant-*` / `.pd-gov-*` / `.pd-auto-*`.

## 8. Límites actuales (no implementado)

- automatizaciones ejecutables / scheduler;
- tool calling / ejecución segura de código;
- historial persistente del Copilot;
- persistencia remota / multiusuario;
- router semántico con LLM (hoy determinista);
- alineación completa `theme.py` ↔ tokens minerales;
- retokenización profunda Plotly / landing marketing;
- QA visual exhaustivo en viewports reales.

## 9. Próximos pasos inmediatos

1. Consumir `paradigm_pending_task` dentro del wizard Assistant.
2. Alinear `theme.py` / config.toml a hex minerales.
3. Migrar restos de landing y charts a tokens.

## 10. Cierre

Estado operativo: topbar mineral, sidebar secundaria, Home aprobada, Assistant/Copilot/Automation/Governance migrados, helpers huérfanos resueltos, docs alineadas al lenguaje mineral.
