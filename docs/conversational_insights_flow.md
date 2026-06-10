# Flujo de AI Conversational Insights

Paradigm incluye una capa de **analista conversacional determinística** (sin LLM): detecta el schema del dataset, hace preguntas guiadas orientadas a causas raíz y genera análisis, gráficos Plotly y recomendaciones priorizadas por impacto.

## Dónde probarlo

| App | Comando | Fuente de datos |
|-----|---------|-----------------|
| **Streamlit v2** (recomendado) | `streamlit run streamlit_app.py` | Demo consultorio, sintético por dominio o CSV/Excel propio |
| **Legacy v1** | `streamlit run legacy/app/main.py` | Upload, demo consultorio o sintético |

En v2, elegí **AI Conversational Insights** en la barra lateral.

## Flujo lineal

```text
Landing (demo | sintético | upload)
  → [Cargar y Comenzar Análisis]
  → Preview (shape, columnas, tipos)
  → Wizard (máx. 3 preguntas: objetivo + hipótesis + segmento sospechoso)
  → Auto-análisis contextual
  → Resultados (resumen, hallazgos, gráficos, recomendaciones priorizadas)
  → Re-analizar / chat libre
```

Progreso visible en cada etapa: *Cargando datos…*, *Detectando estructura…*, *Preparando preguntas…*, *Entendiendo tu objetivo…*, *Generando análisis contextual…*.

## Wizard (máx. 3 preguntas)

1. **Siempre:** objetivo o pregunta de negocio (texto libre).
2. **Hipótesis de causa:** qué métrica preocupa y por qué creés que ocurre (texto libre).
3. **Segmento sospechoso:** dimensión donde esperás concentración del problema (select según schema).

Botón secundario: **Explorar sin cuestionario** (análisis con objetivo genérico).

## Fuentes de datos (v2)

| Opción | Descripción |
|--------|-------------|
| Dataset demo | CSV plano del consultorio (`legacy/data/sample/medical_clinic/`) |
| Datos aleatorios | Generador en `app/conversational/synthetic.py` con patrones analizables |
| Upload | CSV o Excel (`.csv`, `.xlsx`, `.xls`) |

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

- `app/conversational/` — dominio, preguntas, plan, análisis, plots, synthetic, flow
- `app/data.py` — `prepare_dataset_context`, carga CSV/demo
- `app/ui.py` — progreso, cuestionario, resultados
- `legacy/app/core/ai_analytics/` — motor Q&A reactivo (seguimiento conversacional)

## Limitaciones

- Sin modelos de lenguaje: heurísticas basadas en schema y reglas.
- Los filtros del sidebar legacy **no** aplican al analista conversacional (dataset completo cargado).
