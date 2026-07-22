# Capa conversacional Decide (prescriptive)

**Fecha:** 2026-07-22
**Código:** `app/conversational/decision_layer.py` (hook en `generate_insights`)
**Motor:** `paradigm.prescriptive`
**UI:** sin cambios (Streamlit sigue consumiendo `AnalystResult`)

---

## 1. Arquitectura

```text
Usuario (chat / fetch_llm_insight)
        │
        ▼
generate_insights(query)
        │
        ├─ classify_decision_intent ──► who_to_contact | why_priority
        │                               which_policy | cost_sensitivity
        │                                      │
        │                                      ▼
        │                         run_prescriptive_engine / what-if
        │                                      │
        │                                      ▼
        │                         AnalystResult (used_llm=False)
        │                         + evidence en explanation/raw_response
        │                         log operation=decision_prescriptive
        │
        └─ (si not_decision) → LLM o fallback heurístico habitual
```

---

## 2. Intents

| Intent | Ejemplos de consulta |
|--------|----------------------|
| `who_to_contact` | “¿A quiénes debería contactar hoy?” |
| `why_priority` | “¿Por qué esta cita APT-01226 tiene prioridad?” |
| `which_policy` | “¿Qué política se está usando?” |
| `cost_sensitivity` | “¿Qué cambia si aumenta el costo?” |

---

## 3. Etiquetas de claim

Toda respuesta Decide marca bloques:

- `[DATO]` — capacidad, política, parámetros, IDs
- `[PREDICCIÓN]` — riesgo / uplift / ENV
- `[SIMULACIÓN]` — what-if de costo
- `[RECOMENDACIÓN]` — a quién contactar (operativo, no mecanismo del no-show)

No se afirman mecanismos del tipo “X causa el no-show”.

---

## 4. Logging

`log_llm_interaction(..., operation="decision_prescriptive")` con:

- `used_llm=False`
- `sources` incluye `prescriptive:engine`, `decision_intent:*`, `claim:*`
- `raw_response` JSON con `intent` + `evidence`

---

## 5. Fallback

Funciona con `PARADIGM_LLM_PROVIDER=disabled`: Decide no depende del LLM.

---

## 6. Reproducir

```bash
python -c "from app.conversational.llm_service import generate_insights; print(generate_insights('¿A quiénes debería contactar hoy?').insight)"
pytest tests/test_conversational_decision_layer.py -v
```
