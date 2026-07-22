# Paradigm — Portfolio case study

**Producto:** Decision Intelligence Laboratory
**Dominio:** operaciones ambulatorias (datos 100 % sintéticos)
**Versión demo:** 2.2 · 2026-07-22
**Arquitectura:** [`FINAL_ARCHITECTURE.md`](FINAL_ARCHITECTURE.md)

---

## 1. Elevator pitch (30 s)

Paradigm es un laboratorio reproducible que lleva **evidencia gobernada** hasta **opciones de decisión** (a quién contactar, bajo qué política, con qué incertidumbre), sin fingir causalidad clínica ni automatizar campañas. Demuestra el ciclo **Observe → Predict → Explain → Decide → Learn** con mart SQLite, ML honesto, motor prescriptivo y demo Streamlit.

---

## 2. Problema de negocio

| Dolor | Por qué importa |
|-------|-----------------|
| No-shows y cancelaciones tardías | Slots vacíos e ingreso perdido |
| Agenda sin priorización | Recordatorios genéricos, no ranking |
| KPIs inconsistentes entre equipos | Desconfianza en el tablero |
| BI sin puente a la acción | Se ve el pasado; no se decide el contacto de hoy |

---

## 3. Solución (laboratorio, no producto clínico)

1. **Observe** — Generador sintético dimensional → mart SQLite → calidad + KPIs + BI.
2. **Predict** — Ranking no-show (mart) + lab v2 con señal controlable + forecast.
3. **Explain** — SHAP + analista conversacional (LLM opcional / heurística).
4. **Decide** — `paradigm.prescriptive` + chat Decide (capacidad, ENV, sensibilidad de costo).
5. **Learn** — Runs en `ml/experiments/runs/`, tests, CI core.

---

## 4. Resultados que conviene mostrar

### Operativos (mart)

- 520 citas · no-show 13 % · cancelación 18,7 % · ~6,9 M ARS facturados · brecha billing 31.
- 14 checks de calidad (1 WARN esperado de conciliación).

### Metodológicos (ML)

- Pipeline con target, anti-leakage, split temporal y métricas de ranking.
- En mart sintético: AUC débil **declarado** (~0,40–0,42) — honesty > vanity.
- En lab `signal_moderate`: AUC ~0,65 — demuestra que el método responde a señal.

### Decide

- Política operativa tip. `risk` cuando uplift no está disponible / calidad baja.
- Capacidad (p. ej. 30) y what-if de costo → `none` si C es demasiado alto.
- Respuestas chat etiquetadas `[DATO]` / `[PREDICCIÓN]` / `[SIMULACIÓN]` / `[RECOMENDACIÓN]`.

---

## 5. Guion de demo (8–10 min)

| Min | Qué mostrar | Mensaje |
|-----|-------------|---------|
| 0–1 | Landing | “Decision Intelligence Laboratory”, no dashboard genérico |
| 1–3 | Executive Overview + Conciliación | Observe: KPIs + brecha atención–billing |
| 3–5 | No-Show ML + SHAP | Predict/Explain: priorización + límites |
| 5–7 | Chat: “¿A quiénes debería contactar hoy?” | Decide: ranking + política + capacidad |
| 7–8 | “¿Qué cambia si aumenta el costo?” | Sensibilidad / simulación |
| 8–10 | `reports/quality_report.md` o CI | Learn: evidencia regenerable |

Consultas Decide útiles:

- ¿A quiénes debería contactar hoy?
- ¿Por qué esta cita APT-… tiene prioridad?
- ¿Qué política se está usando?
- ¿Qué cambia si aumenta el costo?

---

## 6. Ecosistema de portfolio

| Pieza | Aporte |
|-------|--------|
| **ClarusFlow** | Prepara datos (calidad, contratos, listos para mart/BI). |
| **LumenVox** | Interpreta lenguaje (NL → análisis / SQL). |
| **Paradigm** | Convierte evidencia en decisiones (este repo). |

Narrativa conjunta: *dato preparado → lenguaje interpretado → decisión con evidencia*.

---

## 7. Qué no decir en entrevista

- “Predice no-shows en producción con AUC X”.
- “El modelo causa / evita el no-show”.
- “Automatizamos el contacto a pacientes”.
- Ocultar el AUC débil del mart sintético.

---

## 8. Evidencia en repo

| Artefacto | Uso |
|-----------|-----|
| `reports/quality_report.md` | Confianza Observe |
| `ml/experiments/metrics.json` | Cableado de evaluación (no trofeo) |
| `docs/PRESCRIPTIVE_ENGINE.md` | Contrato Decide |
| `docs/CONVERSATIONAL_DECISION_LAYER.md` | Chat Decide |
| `assets/dashboards/powerbi_executive.png` | BI ejecutivo |
| `tests/` | Learn / regresión |

Checklist operativo: [`portfolio.md`](portfolio.md).
Publicación: [`PUBLICATION_AUDIT.md`](PUBLICATION_AUDIT.md).
