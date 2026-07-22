# Paradigm — Arquitectura objetivo

**Fecha:** 2026-07-21
**Entrada:** [`PARADIGM_CURRENT_STATE.md`](PARADIGM_CURRENT_STATE.md) + docs existentes (`architecture.md`, `problem.md`, `analytical_questions.md`, `metrics.md`, `conversational_insights_flow.md`, `ml/README.md`, README).
**Alcance:** definición de arquitectura objetivo.
**Fuera de alcance:** implementación, refactors o archivos adicionales.

---

## 0. Posicionamiento

Paradigm deja de pensarse solo como “pipeline AE + demo Streamlit” y se define como un **laboratorio de inteligencia de decisiones** sobre operaciones ambulatorias sintéticas.

El laboratorio organiza el valor analítico en cinco capas:

```text
Observe → Predict → Explain → Decide → Learn
```

Cada capa produce **artefactos auditables**. La UI (Streamlit, Power BI, Tableau, chat) **consume** esos artefactos; no es la fuente de verdad. Las políticas operativas reales y cualquier automatización de contacto quedan **fuera del repo** (alineado con `problem.md` / `ml/README.md`: evidencia y priorización, no despliegue clínico).

---

## 1. Capas del laboratorio

### 1.1 Observe

| Dimensión | Definición |
|-----------|------------|
| **Propósito** | Gobernar datos, métricas y calidad para responder *qué pasó* y *dónde mirar*, con definiciones auditables. |
| **Preguntas** | T1–T5 de `analytical_questions.md`: tendencias, fricción por segmento, cancelaciones tardías, revenue vs atendidos, brechas de conciliación. También: ¿el mart es íntegro? ¿los KPIs coinciden entre SQL, BI y Streamlit? |
| **Módulos actuales** | Generador sintético v2; `build_sqlite_mart.py`; `sql/ddl`, `sql/views`, `sql/samples`; `paradigm.quality`; exports `bi/`; `validate_executive_kpis.py`; Streamlit Executive Overview / Conciliación; análisis determinístico conversacional (`analysis.py`, wizard); demos BI dual-lens. |
| **Entradas** | `data/synthetic/*.csv` (9 dims + 2 facts); diccionario y `metrics.md`; filtros de periodo/segmento. |
| **Salidas** | `paradigm_mart.db`; vistas KPI; `reports/quality_report.md`; CSVs BI; KPIs/gráficos ejecutivos; hallazgos descriptivos del wizard. |
| **Capacidades faltantes** | Lineage explícito KPI→SQL→UI; materialización de occupancy proxy si se usa en narrativa; validación cruzada Streamlit ↔ DAX ↔ vistas; corrección documental (“11 dims”); tests de contrato de esquema. |
| **Límites metodológicos** | Datos sintéticos ilustrativos; MVP single-site; métricas de proveedor ≠ calidad clínica; ocupación proxy no es capacidad real. |
| **Relación con otras capas** | **Fundación** de Predict/Explain/Decide/Learn. Sin Observe estable, el resto no es auditable. Learn retroalimenta Observe (drift de calidad, regresiones de KPI). |

---

### 1.2 Predict

| Dimensión | Definición |
|-----------|------------|
| **Propósito** | Estimar estados futuros o riesgos *antes* del evento, con split temporal y métricas de ranking/serie — sin confundir correlación con causa. |
| **Preguntas** | T6: ¿qué citas priorizar por riesgo de no-show en el decision point de booking? ¿Cómo evoluciona la demanda diaria (y por especialidad) en el horizonte H? |
| **Módulos actuales** | `python/src/paradigm/ml/*` + `train_no_show.py`; `ml/forecasting/*` + `train_forecast.py`; artefactos en `ml/experiments/`; tabs Streamlit No-Show ML y Forecasting. |
| **Entradas** | Mart (mismas tablas que BI); features sin leakage (`ml/README.md`); series diarias desde `vw_daily_kpis` / `fact_appointment`. |
| **Salidas** | Scores/probabilidades, joblibs, `metrics.json`, forecast CSV/backtest, metadata de experimento. |
| **Capacidades faltantes** | Deps forecast declaradas y defaults que funcionen en clone limpio; un solo home de ML (hoy `paradigm.ml` vs `ml/`); paths relativos en metadata; baselines obligatorias en CI; calibración y umbrales documentados como artefactos. |
| **Límites metodológicos** | AUC ~0.40–0.42 en sintético: **experimento metodológico**, no predictor desplegable; forecast naïve/seasonal con series cortas y SMAPE alto; no es inferencia causal. |
| **Relación con otras capas** | Consume Observe. Alimenta Explain (SHAP, error de forecast) y Decide (scores + demanda como insumos). Learn mide si Predict mejora o se degrada. |

---

### 1.3 Explain

| Dimensión | Definición |
|-----------|------------|
| **Propósito** | Interpretar *por qué* el sistema predice o el periodo se comporta así — en lenguaje operativo, con límites explícitos (asociación ≠ causalidad). |
| **Preguntas** | ¿Qué features mueven el score local/global? ¿Dónde falla el forecast (folds, segmentos)? ¿Qué hallazgo descriptivo explica un KPI? ¿La respuesta del analista conversacional es fiel al mart/docs? |
| **Módulos actuales** | SHAP (`explain.py`, bundle, beeswarm); feature importances; narrativa `ml/experiment_report.md`; gráficos Plotly; AI Analyst (LLM+RAG) + fallback heurístico; SQL Explorer; Evaluation tab / gold set. |
| **Entradas** | Modelos y métricas de Predict; mart y docs gobernados; gold conversacional. |
| **Salidas** | Explicaciones SHAP; informes Markdown; insights LLM/heurísticos con fuentes; reportes de eval (`evaluation_gold_report.json`); logs `llm_interactions.jsonl`. |
| **Capacidades faltantes** | Separar UI de motor de explicación; desacoplar `legacy_bridge`; etiquetar siempre “asociación / no causal”; plantillas de incertidumbre (intervalos, confianza baja); eval LLM en CI. |
| **Límites metodológicos** | SHAP no implica causa; LLM puede alucinar pese a RAG; análisis sobre upload/CSV genérico ≠ verdad del mart gobernado. |
| **Relación con otras capas** | Traduce Observe y Predict a narrativa. **No** sustituye Decide: recomienda investigación o priorización, no política automática. Learn evalúa calidad de explicación (faithfulness, sql_validity). |

---

### 1.4 Decide

| Dimensión | Definición |
|-----------|------------|
| **Propósito** | Convertir evidencia en **opciones de decisión** comparables (priorización, what-if, costo/beneficio estimado), dejando la ejecución humana fuera del sistema. |
| **Preguntas** | Dado el ranking de riesgo y la presión de demanda, ¿qué intervención sugerir por tramo? ¿Qué impacto neto simulado (slots, revenue, costo) bajo incertidumbre? ¿Qué export llevar a una revisión operativa? |
| **Módulos actuales** | `ml/prescriptive/` (recommender + Monte Carlo + export); `business_impact.py`; UI embebida en No-Show ML; matriz acción ilustrativa T1–T6 en `analytical_questions.md`. |
| **Entradas** | Scores Predict; opcional forecast (demanda); perfiles de intervención; supuestos de efectividad/uptake/costo. |
| **Salidas** | Recomendaciones tabuladas; resumen before/after; CSV/MD/ZIP en `reports/prescriptive/`; impacto top-decile ilustrativo. |
| **Capacidades faltantes** | Capa Decide como módulo de dominio separado de la UI; registro de supuestos versionados; separación clara simulación vs “decisión recomendada”; página/ consola Decide (hoy es sección anexa); no hay capa causal que valide efectividad de intervenciones. |
| **Límites metodológicos** | Reglas + Monte Carlo con parámetros asumidos; **no** RCT ni uplift causal; no automatiza campañas; números sintéticos no son ROI real. |
| **Relación con otras capas** | Depende de Predict (+ Observe). Explain debe acompañar cada recomendación. Learn cierra el ciclo midiendo calidad de la recomendación *como artefacto*, no el outcome clínico real (fuera de alcance). |

---

### 1.5 Learn

| Dimensión | Definición |
|-----------|------------|
| **Propósito** | Medir, registrar y mejorar el laboratorio: calidad de datos, modelos, forecast, analista conversacional y supuestos — con gates reproducibles. |
| **Preguntas** | ¿Regresionó un KPI o un check de calidad? ¿Cambió el ranking metric del no-show? ¿El backtest de forecast empeoró? ¿El gold set conversacional bajó? ¿Los experimentos son comparables entre máquinas? |
| **Módulos actuales** | Quality report; `metrics.json` + ExperimentTracker; eval gold + `test_evaluation.py`; `test_llm_integration.py` (fuera de CI); `make build-all`; CI parcial (mart + quality + KPI). |
| **Entradas** | Artefactos de todas las capas; gold sets; seeds; git commit en tracker. |
| **Salidas** | Reportes de calidad/eval; leaderboards; señales de CI; (objetivo) baselines históricas y alertas de drift. |
| **Capacidades faltantes** | CI que cubra ML/forecast/eval; lockfile; paths relativos; suite de tests unificada; “evaluación continua” del README aún no implementada; retiro de scripts huérfanos o su cableado. |
| **Límites metodológicos** | En sintético, Learn valida **proceso y regresiones de pipeline**, no performance de negocio real; sin datos longitudinales reales no hay learning operativo de intervenciones. |
| **Relación con otras capas** | Observa todas. Puede frena Predict/Decide si fallan umbrales. Retroalimenta Observe (contratos) y Explain (métricas de faithfulness). |

---

## 2. Arquitectura objetivo de extremo a extremo

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         SURFACES (consumo)                               │
│  Streamlit lab UI  │  Power BI (Observe)  │  Tableau (Observe)           │
│  Conversational UI (Explain/Learn)  │  Exports Decide (CSV/MD/ZIP)       │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ solo lectura de artefactos
┌──────────────────────────────────▼───────────────────────────────────────┐
│                    CORE (python package unificado)                       │
│                                                                          │
│  Observe   mart · quality · metrics · kpi contracts                      │
│  Predict   no-show scoring · demand forecasting                          │
│  Explain   shap · report builders · conversational engines (no UI)       │
│  Decide    interventions · simulation · decision briefs                  │
│  Learn     experiment tracker · eval harness · CI gates                  │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────────┐
│                 PLATFORM / PIPELINE (scripts + Make/CI)                  │
│  synthetic → mart → quality → bi exports → train predict → eval learn    │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────────┐
│  GOVERNED STORE: synthetic CSVs · SQLite mart · experiments/ · reports/  │
│  DOCS AS DATA: metrics · dictionary · analytical questions · gold sets   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Regla de borde:** `app/` orquesta UI; la lógica de dominio migra hacia el core. `legacy/` no forma parte del camino feliz del laboratorio.

---

## 3. Separación explícita de modos analíticos

Hoy conviven en la misma demo. El objetivo es **nombrarlos y no mezclar claims**.

| Modo | Pregunta típica | Qué está permitido afirmar | Dónde vive hoy | Dónde debe vivir |
|------|-----------------|----------------------------|----------------|------------------|
| **Análisis descriptivo** | ¿Qué pasó? ¿Dónde se concentra? | Hechos y tasas según `metrics.md` | Mart, views, BI, Overview/Conciliación, wizard determinístico | **Observe** (+ Explain narrativo) |
| **Predicción** | ¿Qué probablemente ocurra / a quién rankear? | Probabilidad o score con métricas de hold-out/backtest; incertidumbre | No-show ML, forecasting | **Predict** |
| **Inferencia causal** | ¿Qué efecto tiene la intervención X? | Solo con diseño causal explícito | **Ausente** (SHAP/reglas no son causal) | Capa futura opcional bajo Explain/Decide; **no** reclamarla hasta existir |
| **Simulación** | ¿Qué pasaría si… bajo supuestos S? | Distribuciones condicionales a S; sensibilidad | Monte Carlo prescriptive | **Decide** (submódulo simulate), inputs etiquetados como supuestos |
| **Decisión prescriptiva** | ¿Qué opción preferir bajo criterios C? | Recomendación rankeada + trade-offs; **humano decide** | Recommender + business impact | **Decide** (recommend/brief); nunca auto-ejecución |

**Anti-patrones a evitar en la arquitectura objetivo:**

- Presentar SHAP como “causa del no-show”.
- Presentar Monte Carlo como “ROI validado”.
- Presentar el LLM como fuente de KPIs (debe citar mart/SQL/docs).
- Mezclar upload CSV genérico con KPIs gobernados del mart sin etiqueta de contexto.

---

## 4. Ubicación propuesta de capacidades

| Capacidad | Capa(s) primaria(s) | Rol en la arquitectura objetivo |
|-----------|---------------------|----------------------------------|
| **BI (Power BI / Tableau)** | Observe | Lentes ejecutivo/diagnóstico sobre la misma verdad; no entrenan modelos; evidencian T1–T5. |
| **ML no-show** | Predict → Explain → Decide | Score de priorización; SHAP en Explain; ranking alimenta Decide. |
| **Forecasting** | Predict → Explain → Decide | Demanda futura; error/backtest en Explain; presión de demanda como input de simulación. |
| **IA conversacional** | Explain (+ Observe para SQL sobre hechos) | Interfaz de indagación y narrativa; motor en core; UI en `app/`. Gold/eval en **Learn**. |
| **Evaluation** | Learn | Gate de calidad del analista, de modelos y del pipeline; CI ampliado. |
| **Quality / KPI validate** | Observe + Learn | Observe produce checks; Learn los exige en CI. |
| **Prescriptive / what-if** | Decide | Recomendación + simulación; export para revisión humana. |

---

## 5. Destino de componentes actuales

Leyenda de acciones: **Conservar** · **Reorganizar** · **Aislar** · **Depreciar**.

### Conservar (núcleo del laboratorio)

- Modelo dimensional 9+2, DDL/views, generador v2, mart SQLite.
- `paradigm.quality` (14 checks) y validación de KPIs.
- Exports BI dual-lens + DAX/instrucciones (sin exigir binarios en git).
- Experimento no-show con framing honesto (target, leakage, split temporal).
- Forecasting package + ExperimentTracker (con endurecimiento de deps).
- Prescriptive recommender + Monte Carlo (como simulación de Decide).
- Streamlit v2 como superficie principal del lab.
- Gold set conversacional y métricas de evaluación.
- Documentación de problema, métricas y preguntas tronco (T1–T6).

### Reorganizar

- Unificar ML bajo un solo árbol de dominio (p. ej. core `predict/` / `forecasting/` / `prescriptive/`), dejando `scripts/` como CLI delgados.
- Extraer de `app/conversational/` los motores (NL→SQL, analysis, eval, RAG) hacia core Explain/Learn; dejar en `app/` solo render.
- Separar UI de Decide de la pestaña No-Show (misma app, sección/navegación propia alineada a la capa).
- Alinear docs (`architecture.md`, README Live Demo, `flow.mmd`, conversational “3 pestañas”) con la realidad 9 dims / 5 páginas / 4 tabs.
- Declarar deps de forecast y arreglar orden Docker COPY; introducir lock o pins.
- Metadata de experimentos con paths relativos al repo.

### Aislar

- `legacy/` completo: dejar de ser dependencia runtime de v2; bridge solo detrás de flag o carpeta `compat/` temporal.
- Generador `generate_medical_clinic_data.py` y samples flat: solo para demos legacy aisladas.
- Upload/CSV genérico y dominios sintéticos no-mart: modo “sandbox analyst”, etiquetado distinto del lab gobernado.
- Scripts huérfanos (`verify_dynamic_questions.py`) y tests de notebooks sin notebooks: aislar o cablear explícitamente.
- Placeholders vacíos (`data/raw`, `ml/features`, etc.): o se usan con contrato o se documentan como reservados.

### Depreciar (gradual, sin big-bang)

- App Streamlit v1 como entrada recomendada (ya marcada opcional; retirar del happy path).
- Narrativa “11 dims + 2 facts” y badge que implique Live Demo hospedado si no existe.
- Claim implícito de Prophet/Holt-Winters “listos” sin deps.
- Roadmap vendido como hecho (“evaluación continua en CI”) hasta que Learn lo implemente.
- Dependencia estructural `legacy_bridge` (depreciar tras migración de `core` útil al package).

---

## 6. Migración incremental (sin reescritura total)

Principio: **cada etapa deja el lab usable**; no se reescribe Streamlit ni el mart de un golpe.

### Etapa A — Alinear verdad y claims (docs + gates mínimos)

Corregir dims/tabs/arquitectura en documentación; fijar framing Observe→…→Learn en docs canónicos; ampliar CI solo con lo que ya es estable (tests evaluation + quality ya existentes). Sin mover carpetas grandes.

### Etapa B — Plataforma reproducible

Declarar deps forecast; arreglar Docker; paths relativos en tracker; opcional lockfile; `make`/`build-all` como camino documentado único.

### Etapa C — Separar core y UI (Explain/Predict primero)

Mover motores conversacionales y unificar imports ML detrás de APIs internas; `app/` pasa a llamar core; `legacy_bridge` queda aislado o feature-flagged.

### Etapa D — Nombrar Decide y Learn en producto

Navegación Streamlit alineada a capas (o secciones explícitas); Decide con supuestos versionados; Learn con eval gold + subset ML/forecast en CI.

### Etapa E — Depreciar legacy y ruido

Retirar happy path v1; archivar generador flat; limpiar placeholders/huérfanos; actualizar portfolio reveal order al ciclo de cinco capas.

**No hacer:** rewrite total a monorepo nuevo, cambiar de Streamlit a otro UI framework, ni introducir causal ML hasta tener diseño y datos adecuados.

---

## 7. Principios arquitectónicos

| Principio | Implicación concreta |
|-----------|----------------------|
| **Reproducibilidad** | Seed, split temporal, CLI versionada, deps declaradas, paths relativos, regenerar mart/modelos desde scripts. |
| **Trazabilidad** | Pregunta → KPI (`metrics.md`) → SQL/view → artefacto BI/ML → pantalla; experiment_id en salidas Decide/Explain. |
| **Auditabilidad** | Quality report, logs LLM, gold eval, DAX/docs; claims etiquetados por modo analítico (§3). |
| **Separación core / UI** | Streamlit/BI no contienen reglas de negocio nuevas; orquestan y visualizan. |
| **Evidencia antes que automatización** | Rankings, what-if y briefs; **cero** outreach automático; humano en el loop (ya en `architecture.md` / `ml/README.md`). |
| **Incertidumbre explícita** | Mostrar métricas débiles (AUC, SMAPE), intervalos/supuestos de simulación, estado LLM (RAG vs heurístico), y límites del sintético en toda superficie Decide/Explain. |

---

## 8. Tabla — componentes actuales → capas objetivo

| Componente actual | Capa objetivo | Acción propuesta | Justificación |
|-------------------|---------------|------------------|---------------|
| `data/synthetic` + generador v2 | Observe | Conservar | Fuente gobernada reproducible del lab |
| `sql/ddl`, `sql/views`, samples | Observe | Conservar | Contrato dimensional y KPIs |
| `paradigm.quality` + `run_data_quality.py` | Observe / Learn | Conservar | Integridad del mart; gate de Learn |
| `validate_executive_kpis.py` | Observe / Learn | Conservar | Consistencia numérica de KPIs |
| `bi/powerbi`, `bi/tableau` | Observe | Conservar | Lentes ejecutivo/diagnóstico; misma verdad |
| Streamlit Executive / Conciliación | Observe | Conservar | Superficie lab para T1–T5 |
| `paradigm.ml` + `train_no_show.py` | Predict / Explain | Reorganizar | Unificar home ML; SHAP = Explain |
| `ml/forecasting` + `train_forecast.py` | Predict / Explain | Reorganizar + endurecer deps | Predicción de demanda; hoy frágil out-of-box |
| `ml/experiments` + tracker | Predict / Learn | Reorganizar | Paths relativos; comparación de runs |
| SHAP / `business_impact.py` | Explain / Decide | Conservar (separar claims) | Explicación vs impacto ilustrativo |
| `ml/prescriptive/*` | Decide | Reorganizar (UI propia) | Simulación + recomendación ≠ predicción |
| Wizard + `analysis.py` determinístico | Observe / Explain | Reorganizar → core | Descriptivo gobernado sin LLM |
| NL→SQL, RAG, `llm_service` | Explain | Reorganizar → core | Narrativa/indagación; no source of KPIs |
| Evaluation gold + `test_evaluation.py` | Learn | Conservar + cablear CI | Gate del analista |
| `test_llm_integration.py` | Learn | Conservar + incluir en gate | Seguridad/fallback |
| `legacy/` + `legacy_bridge` | — (compat) | Aislar → Depreciar | Rompe separación core/UI y “legacy opcional” |
| Generador clinic flat / samples v1 | — | Aislar / Depreciar | Paralelo al mart v2 |
| `streamlit_app.py` / `app/*` UI | Surfaces | Conservar shell; adelgazar | UI no debe ser dominio |
| App Streamlit v1 | Surfaces | Depreciar | Fuera del happy path del lab |
| `verify_dynamic_questions.py` | Learn (potencial) | Aislar o cablear | Hoy huérfano |
| Placeholders vacíos | — | Aislar / limpiar | Reducen claridad del mapa |
| CI actual | Learn | Reorganizar (ampliar) | Hoy no cubre Predict/Explain/Decide |
| Docs architecture / README claims | Transversal | Reorganizar | Deben reflejar 5 capas y hechos reales |

---

## 9. Tabla — etapas de migración

| Etapa de migración | Alcance | Dependencias | Criterio de cierre |
|--------------------|---------|--------------|--------------------|
| **A. Alinear verdad** | Corregir docs (dims, tabs, arquitectura, Live Demo); introducir mapa Observe→Learn en docs canónicos; CI + `test_evaluation` (mínimo) | Ninguna de código estructural | Docs coherentes con `PARADIGM_CURRENT_STATE`; CI verde con quality + KPI + eval test |
| **B. Plataforma reproducible** | Deps forecast; Docker COPY; paths relativos en experimentos; pins/lock opcional; defaults que entrenan en clone limpio | Etapa A (claims honestos) | `train_forecast` y `train_no_show` documentados y ejecutables sin install ad-hoc; metadata portable |
| **C. Core ↔ UI** | Extraer motores conversational/ML a package; `app` solo render; flag/aislamiento de `legacy_bridge` | Etapa B | v2 funciona sin import runtime de `legacy/app` en el happy path; tests de motores sin Streamlit |
| **D. Decide + Learn de producto** | Navegación/secciones por capa; Decide con supuestos versionados; CI con subset predict/forecast/eval | Etapa C | Usuario recorre Observe→…→Learn en demo; CI falla si regresionan métricas/gates acordados |
| **E. Depreciación** | Retirar v1 del README happy path; archivar flat generator; limpiar huérfanos/placeholders; portfolio reveal = 5 capas | Etapa D estable | `legacy` no requerido para demo; mapa de repo sin módulos “fantasma” |

---

## 10. Relación con la documentación existente

| Documento actual | Rol tras adoptar esta arquitectura |
|------------------|-------------------------------------|
| `PARADIGM_CURRENT_STATE.md` | Baseline factual (as-is) |
| `architecture.md` | Debe evolucionar a apuntar este target (Observe…Learn) sin borrar el lineage técnico mart→BI |
| `analytical_questions.md` | Sigue siendo el tronco T1–T6; T1–T5→Observe, T6→Predict/Decide |
| `metrics.md` / `data_dictionary.md` | Contratos de Observe y corpus de Explain (RAG) |
| `conversational_insights_flow.md` | Flujo de superficie Explain; actualizar a 4 tabs y borde core/UI |
| `ml/README.md` | Contrato metodológico de Predict (+ límites) |
| `portfolio.md` | Reveal order alineado a cinco capas, no solo PBI→Tableau→ML |

---

*Documento de arquitectura objetivo. No implementa cambios de código ni crea otros archivos.*
