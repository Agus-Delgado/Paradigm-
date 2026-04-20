# Paradigm v2 — Preguntas analíticas troncales y trazabilidad

Este documento es el **eje conceptual** del marco analítico: define **preguntas troncales**, la **matriz** hacia KPIs, SQL, consumo BI y posibles acciones, **casos de decisión** concretos, una **plantilla de explicabilidad liviana** para la capa predictiva, y la **frontera** entre lo documentado hoy y el trabajo técnico futuro.

Los datos del repo son **sintéticos**; las respuestas numéricas son **ilustrativas**. El valor está en **definiciones, trazabilidad y narrativa defendible**.

**Relación con otros documentos:** las definiciones normativas de KPIs están en [`metric_definitions.md`](metric_definitions.md); el modelo dimensional y el flujo técnico en [`architecture.md`](architecture.md); el relato de negocio en [`business_case.md`](business_case.md); el modelo de no-show en [`ml/README.md`](../ml/README.md).

---

## 1. Preguntas diagnósticas troncales

Cada troncal tiene un **id** (T1–T6) usado en el resto del documento y en [`business_case.md`](business_case.md).

| Id | Pregunta troncal | Lectura de decisión (si se observa el patrón) |
|----|-------------------|-----------------------------------------------|
| **T1** | ¿Cómo evolucionan en el tiempo **no-show**, **cancelación**, **citas atendidas** y el volumen operativo agregado? | Si empeoran tasas o cae volumen atendido, **revisar políticas de agenda** y **comunicación** antes de optimizar franjas puntuales. |
| **T2** | ¿**Dónde** se concentra la fricción operativa por **especialidad**, **canal de reserva** y **tiempo** (día, franja)? | Si un corte sistemáticamente dispara tasas o caída de asistencia, **profundizar reglas de oferta**, **canales** o **capacidad percibida** en ese segmento. |
| **T3** | ¿Dónde se concentran las **cancelaciones tardías** (menos de 24 h antes del turno) y en qué combinaciones canal–servicio? | Si la cancelación tardía es alta, **ajustar ventanas de reprogramación**, **recordatorios** o **reglas de liberación de cupo** (siempre como decisión de negocio; aquí solo señal). |
| **T4** | ¿Cómo evoluciona el **ingreso facturado** y cómo se relaciona con citas **atendidas** en la ventana analizada? | Si divergen ingreso y actividad atendida, **revisar ciclo de facturación** o **lag** entre turno y emisión, no solo “vender más turnos”. |
| **T5** | ¿Qué **brechas** hay entre **citas atendidas** y **líneas de facturación** (conciliación)? | Si crece lo pendiente o “atendido sin facturación”, **revisar proceso administrativo** y reglas de emisión, no solo KPIs de sala. |
| **T6** | Ante el **riesgo de no-show** en el punto de decisión documentado, **qué citas** conviene priorizar para contacto o seguimiento? | Si se usa el score como apoyo, **ordenar esfuerzo operativo** (p. ej. recordatorios) sin sustituir criterio humano ni políticas internas. |

**Nota (T1 y ocupación):** la **ocupación (proxy)** está definida en [`metric_definitions.md`](metric_definitions.md) pero **no está materializada en una vista SQL** en el estado actual del repo (ver [`sql/README.md`](../sql/README.md)). La lectura de utilización puede apoyarse en **KPIs de volumen y tasas** en vistas existentes y, si se implementa, en **BI** con la regla proxy documentada.

---

## 2. Matriz pregunta → KPI / vista SQL / visual / posible acción

**Convenciones:** “KPI” remite al diccionario [`metric_definitions.md`](metric_definitions.md) (apartados numerados bajo cada métrica). Las vistas son las de [`sql/README.md`](../sql/README.md). Los CSV de exportación nombran el **rol** del consumo; el detalle de columnas está en cada carpeta `bi/`.

| Id | KPIs principales (referencia) | Vista SQL y/o muestra | Power BI (ejecutivo) | Tableau (diagnóstico) | Posible acción operativa (ilustrativa) |
|----|------------------------------|------------------------|------------------------|-------------------------|----------------------------------------|
| **T1** | No-show rate; cancelación; citas atendidas; tendencia diaria (diccionario: apartados 2, 3 y 5) | `vw_daily_kpis`; `sql/samples/03_attended_by_month.sql` | `DailyKpis.csv`: tendencia KPIs periodo; lectura “¿qué pasa?” | `DailyKpis.csv` / cortes en historias: tendencia y comparación | Reunión de seguimiento; revisar metas de tasa si persisten desvíos |
| **T2** | No-show, cancelación, productividad por especialidad/canal (apartados 2, 3, 11 y 12) | `vw_kpis_by_specialty`; `sql/samples/01_no_show_by_specialty.sql`; `sql/samples/02_cancellation_by_channel.sql` | `KpiBySpecialty.csv`: ranking/agregado mensual por especialidad | `KpiBySpecialty.csv`, `AppointmentBase.csv`: ranking, canal, especialidad, exploración | Focalizar canal o especialidad con peor desempeño; revisar cupos o comunicación |
| **T3** | Cancelación tardía; cancelación (apartados 4 y 3) | `vw_appointment_base` (fechas/horas para regla **menos de 24 h** antes del turno); `sql/samples/02_cancellation_by_channel.sql` donde aplique | **Power BI (MVP):** cancelación tardía **fuera** del lienzo ejecutivo — ver [`bi/powerbi/README.md`](../bi/powerbi/README.md) | **Tableau:** `AppointmentBase.csv` y guía en [`bi/tableau/README.md`](../bi/tableau/README.md) (cancelación tardía) | Ajustar recordatorios o políticas de cancelación en segmentos críticos |
| **T4** | Ingreso facturado; ingreso por cita atendida (apartados 6 y 8) | `vw_kpis_by_specialty` / `vw_kpis_by_provider` (`revenue_facturado_mes`); `sql/samples/04_billing_by_month.sql` | Tendencia ingreso vs actividad si el diseño ejecutivo lo muestra (`RevenueBridge.csv`, KPIs) | `RevenueBridge.csv`, series por tiempo | Revisar desfases entre actividad y facturación mensual |
| **T5** | Conciliación atención vs facturación (apartado 9) | `vw_revenue_bridge`; `sql/samples/05_reconciliation_attendance_vs_billing.sql` | Puente / buckets vía `RevenueBridge.csv` en medidas DAX | Misma fuente: exploración de `reconciliation_bucket` | Priorizar corrección de emisiones pendientes o inconsistencias |
| **T6** | No-show rate (contexto); **score** ML no es KPI de negocio sino **priorización** | Mismo mart que BI: features desde tablas del mart (ver [`ml/README.md`](../ml/README.md)); sin vista dedicada al score en SQL | No sustituye KPIs: el tablero ejecutivo sigue siendo histórico | Análisis combinado posible en demo (score exportado offline si se implementa en futuro) | Lista priorizada para **recordatorios** o revisión manual; **no** automatización en el repo |

---

## 3. Casos de decisión concretos

Formato fijo: **disparador** → **rol** → **artefacto** → **decisión típica** → **límite honesto**.

### UC1 — Seguimiento ejecutivo de tasas

| Campo | Contenido |
|-------|-----------|
| **Disparador** | Suba sostenida de la **tasa de no-show** o de la **tasa de cancelación** en `vw_daily_kpis` / `DailyKpis.csv` respecto al periodo anterior. |
| **Rol** | Dirección / operaciones. |
| **Artefacto** | Power BI ejecutivo (`bi/powerbi/`); validación alineada a [`metric_definitions.md`](metric_definitions.md). |
| **Decisión típica** | Acordar **revisión focalizada** (canal, especialidad) y seguimiento en la siguiente ventana. |
| **Límite** | Datos sintéticos; sin umbral “óptimo” universal; el repo no define políticas. |

### UC2 — Diagnóstico por especialidad y canal

| Campo | Contenido |
|-------|-----------|
| **Disparador** | Una **especialidad** o **canal** aparece como outlier en `vw_kpis_by_specialty` o muestras `01` / `02`. |
| **Rol** | Jefatura de servicio / recepción (operativo). |
| **Artefacto** | Tableau analítico (`bi/tableau/`); `KpiBySpecialty.csv`, `AppointmentBase.csv`. |
| **Decisión típica** | **Profundizar** causa operativa (franja, motivo de cancelación si está en el análisis) antes de cambiar cupos. |
| **Límite** | Asociación observacional; no implica causalidad estadística formal. |

### UC3 — Cancelación tardía

| Campo | Contenido |
|-------|-----------|
| **Disparador** | **Tasa de cancelación tardía** alta en el segmento de interés (regla **menos de 24 h** antes del inicio del turno; ver [`metric_definitions.md`](metric_definitions.md)). |
| **Rol** | Recepción / agenda. |
| **Artefacto** | Consultas sobre `vw_appointment_base` + visualizaciones de hora/canal en Tableau. |
| **Decisión típica** | Proponer **ajuste de recordatorios** o ventanas de cancelación (negocio); el repo solo documenta la señal. |
| **Límite** | Sintético; calibración real requeriría datos productivos. |

### UC4 — Conciliación atención–facturación

| Campo | Contenido |
|-------|-----------|
| **Disparador** | Crecimiento de filas en buckets tipo **atendido sin facturación** o pendiente en `vw_revenue_bridge`. |
| **Rol** | Facturación / administración. |
| **Artefacto** | `sql/samples/05_reconciliation_attendance_vs_billing.sql`; `RevenueBridge.csv` en BI. |
| **Decisión típica** | **Priorizar** corrección de emisiones o revisión de casos; no automatizar cobranza desde el repo. |
| **Límite** | Sin **ingreso cobrado** estricto en MVP; ver [`metric_definitions.md`](metric_definitions.md). |

### UC5 — Priorización ante riesgo de no-show (ML)

| Campo | Contenido |
|-------|-----------|
| **Disparador** | Necesidad de **ordenar** contactos previos al turno con criterio explícito (demo/portfolio). |
| **Rol** | Operaciones / agenda (con supervisión). |
| **Artefacto** | `scripts/train_no_show.py` → `ml/experiments/metrics.json`; importancias en el mismo archivo; [`ml/README.md`](../ml/README.md). |
| **Decisión típica** | Usar **probabilidad** o ranking para **ordenar** recordatorios; el umbral lo define negocio. |
| **Límite** | No es servicio en producción; desempeño puede ser débil en sintético; **no** usar para evaluar personas. |

---

## 4. Plantilla de explicabilidad liviana (capa predictiva no-show)

Usar como checklist al narrar resultados del modelo (entrevista, portfolio o nota interna). Completar con lo publicado en `ml/experiments/metrics.json` y [`ml/README.md`](../ml/README.md).

| Campo | Qué escribir |
|-------|----------------|
| **Señal** | Probabilidad de no-show (o ranking) y unidad de análisis: **una cita** al momento de la reserva. |
| **Universo** | Citas con estado final **ATTENDED** o **NO_SHOW**; canceladas **fuera** del target del modelo. |
| **Punto de decisión** | Inmediatamente después de **reservar**; lista de features permitidas vs leakage en [`ml/README.md`](../ml/README.md). |
| **Evidencia técnica** | ROC-AUC, PR-AUC, Brier; **captura en top decil** (`top_decile` en `metrics.json`) como lectura operativa conceptual. |
| **Explicación local/global** | **Importancias** del Random Forest en `metrics.json`: qué columnas pesan más **en el modelo** (no causalidad). |
| **Riesgos de uso** | Confundir correlación con causa; aplicar score a **evaluación de personas**; confiar en cifras **sintéticas** como si fueran reales. |
| **Acción sugerida (tipo)** | Priorización de **recordatorios** o revisión de lista; **no** ejecución automática en el repo. |

---

## 5. Documentación actual vs trabajo técnico futuro

### 5.1 Queda documentado en el repo (estado actual)

- Definiciones de KPIs y anclajes en [`metric_definitions.md`](metric_definitions.md).
- Mart SQLite, vistas `vw_*` y muestras en `sql/samples/` según [`sql/README.md`](../sql/README.md).
- Exportes CSV y guías de lienzo en `bi/powerbi/` y `bi/tableau/`.
- Pipeline de calidad, validación de KPIs ejecutivos y **un** modelo de no-show reproducible con artefactos en `ml/experiments/`.
- Este documento y enlaces desde [`architecture.md`](architecture.md), [`business_case.md`](business_case.md) y [`README.md`](../README.md).

### 5.2 Posible implementación o profundización posterior (fuera del alcance documental actual)

| Tema | Notas |
|------|--------|
| **Ocupación (proxy) en SQL o medida única** | Hoy definida en métricas; vista dedicada o regla única en BI pendiente de decisión técnica. |
| **Ingreso cobrado** / tesorería | Fuera del MVP; requiere nuevos hechos o fechas de pago. |
| **Multi-sede, slots finos, reprogramaciones encadenadas** | Fuera del MVP; ver [`business_case.md`](business_case.md). |
| **Servicio de inferencia** (API, batch productivo), **automatización** de campañas | Explícitamente fuera; el repo es demo reproducible. |
| **Otros modelos** (p. ej. cancelación) | Línea de evolución mencionada en [`ml/README.md`](../ml/README.md); no comprometido. |
| **Tableros binarios** (`.pbix` / `.twbx`) | Material de demo local; no son el contrato del repo. |

---

## 6. Referencia rápida vista ↔ tema

| Vista | Uso principal en troncales |
|-------|----------------------------|
| `vw_daily_kpis` | T1 — tendencia diaria por fecha de turno |
| `vw_kpis_by_specialty` | T2, T4 — cortes por especialidad; ingreso facturado por mes |
| `vw_kpis_by_provider` | T2, T4 — mismo espíritu por profesional (métrica operativa) |
| `vw_appointment_base` | T2, T3 — enriquecido para cortes y lógica temporal |
| `vw_revenue_bridge` | T4, T5 — conciliación y puente de ingreso por cita |
