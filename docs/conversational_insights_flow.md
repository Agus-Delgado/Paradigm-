# Flujo de AI Conversational Insights

Paradigm incluye un **analista conversacional híbrido**: motor determinístico de análisis contextual + **AI Analyst** (LLM + RAG) con fallback heurístico transparente.

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
  → Auto-análisis contextual + primer insight AI Analyst (LLM o heurístico)
  → Workspace con 3 pestañas (ver abajo)
```

Progreso visible: *Cargando datos…*, *Detectando estructura…*, *Generando análisis contextual + AI Analyst…*.

## Arquitectura híbrida

```text
Usuario
  → Wizard / Chat / NL→SQL
       ├─ LLM disponible → RAG (docs + SQL samples) + schema → JSON estructurado
       └─ Fallback       → motor heurístico (nl_to_sql / análisis contextual)
```

| Capa | Rol |
|------|-----|
| **RAG FAISS** | `data_dictionary.md`, `metrics.md`, `sql/samples/*.sql` |
| **LLM** | Ollama (default), Groq, OpenAI, Grok — ver `.env.example` |
| **Safeguards** | Solo `SELECT`/`WITH`, rate limit, log JSONL auditable |
| **UI** | Banner de estado, **✦ Ask AI Analyst**, chat persistente |

Con `PARADIGM_LLM_PROVIDER=disabled` el flujo es idéntico al modo determinístico original.

## Workspace post-análisis (3 pestañas)

| Pestaña | Contenido |
|---------|-----------|
| **Análisis Guiado** | Insight LLM post-wizard, análisis contextual, gráficos, chat AI |
| **SQL Explorer** | NL→SQL híbrido (LLM + comparación heurística), editor, historial |
| **Data Explorer** | Filtros, preview, **Explorar con IA**, **Ask AI Analyst** |

En las tres pestañas: banner LLM, botón **✦ Ask AI Analyst** y panel de chat compartido (`session_state`).

## Wizard (máx. 3 preguntas)

1. **Siempre:** objetivo o pregunta de negocio (texto libre).
2. **Hipótesis de causa:** qué métrica preocupa y por qué creés que ocurre (texto libre).
3. **Segmento sospechoso:** dimensión donde esperás concentración del problema (select según schema).

Botón secundario: **Explorar sin cuestionario**.

Tras el wizard, `generate_insights()` produce: insight, recomendación, impacto, confianza, fuentes y SQL opcional con gráfico automático.

## SQL Explorer

- Tabla SQLite en memoria: `data` (solo lectura).
- **NL → SQL:** `generate_sql_llm_enhanced()` — LLM + RAG con fallback a heurísticas.
- Badge **LLM + RAG** vs **Heurístico**; expander de comparación cuando difieren.
- Validación reforzada: `validate_llm_sql()` (una sentencia, sin DDL/DML).

## AI Analyst — chat y logging

- Chat persistente vía **✦ Ask AI Analyst** (hasta 20 turnos en memoria de sesión).
- Log auditable: `data/processed/llm_interactions.jsonl` (query, respuesta, `duration_ms`, tokens aprox.).
- Sidebar: toggle **Ver Historial AI** (o `PARADIGM_DEBUG=true`).
- Rate limit: `PARADIGM_LLM_RATE_LIMIT` (default 10/min).

## Data Explorer

- Filtros dinámicos, preview, stats rápidas.
- **Explorar con IA:** subset filtrado → Análisis Guiado.
- Mismo chrome AI Analyst que el resto del workspace.

## Fuentes de datos (v2)

| Opción | Descripción |
|--------|-------------|
| Dataset demo | CSV plano del consultorio |
| Datos aleatorios | `app/conversational/synthetic.py` |
| Upload | CSV o Excel |

## Módulos

| Módulo | Responsabilidad |
|--------|-----------------|
| `app/conversational/flow.py` | Landing, wizard, tabs |
| `app/conversational/ai_analyst_ui.py` | Banner, chat, sidebar historial |
| `app/conversational/llm_service.py` | LLM + RAG + orquestación |
| `app/conversational/llm_security.py` | Validación SQL, rate limit |
| `app/conversational/llm_logging.py` | JSONL estructurado |
| `app/conversational/nl_to_sql.py` | NL→SQL híbrido |
| `app/conversational/sql_explorer.py` | UI SQL |
| `app/config/llm_config.py` | Proveedores y env vars |

## Limitaciones

- Rate limit en memoria del proceso (demo/portfolio; no multi-usuario productivo).
- SQL Explorer: tabla fija `data`; datasets grandes pueden ser lentos en memoria.
- Sin PHI — datos 100 % sintéticos.
- Filtros del sidebar ejecutivo **no** aplican al analista conversacional.
