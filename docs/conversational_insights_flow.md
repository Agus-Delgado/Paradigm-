# Flujo de AI Conversational Insights

Paradigm incluye una capa de **analista conversacional determinística** (sin LLM): detecta el schema del dataset, hace preguntas guiadas orientadas a causas raíz y genera análisis, gráficos Plotly y recomendaciones priorizadas por impacto.

## Dónde probarlo

| App | Comando | Fuente de datos |
|-----|---------|-----------------|
| **Streamlit v2** (recomendado) | `streamlit run streamlit_app.py` | Demo consultorio, sintético por dominio o CSV/Excel propio |
| **Legacy v1** | `streamlit run legacy/app/main.py` | Upload, demo consultorio o sintético |

En v2, elegí **AI Conversational Insights** en la barra lateral.

## Flujo lineal (hasta el primer análisis)

```text
Landing (demo | sintético | upload)
  → [Cargar y Comenzar Análisis]
  → Preview (shape, columnas, tipos)
  → Wizard (máx. 3 preguntas: objetivo + hipótesis + segmento sospechoso)
  → Auto-análisis contextual
  → Workspace con 3 pestañas (ver abajo)
```

Progreso visible en cada etapa: *Cargando datos…*, *Detectando estructura…*, *Preparando preguntas…*, *Entendiendo tu objetivo…*, *Generando análisis contextual…*.

## Workspace post-análisis (3 pestañas)

Tras completar el wizard (o **Explorar sin cuestionario**), la UI muestra navegación horizontal persistente (`session_state`):

| Pestaña | Contenido |
|---------|-----------|
| **Análisis Guiado** | Resultados contextuales, re-analizar, chat de seguimiento |
| **SQL Explorer** | NL→SQL, editor, ejecución SQLite en memoria, historial, gráfico auto |
| **Data Explorer** | Filtros dinámicos, preview, stats rápidas, **Explorar con IA** |

## Wizard (máx. 3 preguntas)

1. **Siempre:** objetivo o pregunta de negocio (texto libre).
2. **Hipótesis de causa:** qué métrica preocupa y por qué creés que ocurre (texto libre).
3. **Segmento sospechoso:** dimensión donde esperás concentración del problema (select según schema).

Botón secundario: **Explorar sin cuestionario** (análisis con objetivo genérico).

## SQL Explorer

- El DataFrame cargado se registra en **SQLite `:memory:`** como tabla `data` (stdlib, sin dependencias extra).
- Solo consultas de lectura: `SELECT` / `WITH`.
- **NL → SQL:** heurísticas por intención (`compare`, `detect_anomaly`, `search`, etc.) + resolución de columnas según dominio.
- Editor monospace editable antes de ejecutar.
- Resultados en `st.dataframe` + gráfico Plotly inferido automáticamente.
- Historial de consultas en `session_state` (reusar con un clic).

Ejemplo NL (finanzas sintético): *"muéstrame los clientes con mayor desvío"* → SQL con `ORDER BY desvio_abs DESC` sobre `variacion_pct` / `centro_costo`.

## Data Explorer

- Columna izquierda: lista de columnas con tipo lógico + filtros dinámicos (categórico, numérico, fecha, booleano).
- Columna derecha: métricas de filas filtradas, stats por columna, preview tabular.
- **Explorar con IA:** aplica filtros, crea un `DatasetContext` del subset y salta a **Análisis Guiado** con análisis automático.

## Fuentes de datos (v2)

| Opción | Descripción |
|--------|-------------|
| Dataset demo | CSV plano del consultorio (`legacy/data/sample/medical_clinic/`) |
| Datos aleatorios | Generador en `app/conversational/synthetic.py` con patrones analizables |
| Upload | CSV o Excel (`.csv`, `.xlsx`, `.xls`) |

Las tres pestañas operan sobre el mismo DataFrame cargado (demo, sintético o upload).

## Dominios detectados

| Dominio | Señales | Ejemplo |
|---------|---------|---------|
| `healthcare_clinic` | `estado_turno`, `especialidad`, `ingreso_neto` | Ausencias por especialidad/canal |
| `healthcare_mart` | `status_code`, `appointment_date`, `specialty_name` | No-show por segmento mart |
| `finance` | presupuesto, real, variacion, centro_costo | Desvíos presupuestarios |
| `operations` | planta, linea, defectos, tiempo_ciclo | Defectos por planta/línea |
| `generic` | cualquier CSV | Análisis genérico métrica × segmento |

## Datos sintéticos

El generador crea patrones detectables para demos:

- **Salud:** Cardiología y canal Teléfono con más ausencias.
- **Finanzas:** Planta Logística + Operaciones con desvíos altos; outliers en Marketing.
- **Operaciones:** Planta B con más defectos; turno Noche con ciclos más largos.

## Módulos

- `app/conversational/flow.py` — landing, wizard, tabs post-análisis
- `app/conversational/sql_engine.py` — SQLite en memoria, ejecución segura
- `app/conversational/nl_to_sql.py` — NL → SQL determinístico
- `app/conversational/sql_explorer.py` — UI SQL Explorer
- `app/conversational/data_explorer.py` — UI Data Explorer
- `app/conversational/` — dominio, preguntas, plan, análisis, plots, synthetic
- `app/data.py` — `prepare_dataset_context`, carga CSV/demo
- `app/ui.py` — progreso, cuestionario, resultados
- `legacy/app/core/ai_analytics/` — motor Q&A reactivo (seguimiento conversacional)
- `legacy/app/core/exploration.py` — máscaras de filtro reutilizadas

## Limitaciones

- Sin modelos de lenguaje: heurísticas basadas en schema y reglas (también en NL→SQL).
- SQL Explorer: solo lectura; tabla fija `data`; datasets muy grandes pueden ser lentos en memoria.
- Los filtros del sidebar de otras pestañas v2 **no** aplican al analista; Data Explorer tiene sus propios filtros locales.
- Los filtros del sidebar legacy v1 **no** aplican al analista conversacional.
