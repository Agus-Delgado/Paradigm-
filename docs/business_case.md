# Paradigm v2 — Caso de negocio

## Resumen

**Paradigm v2** es una **demo de inteligencia operativa aplicada** con caso principal en **operación ambulatoria** (consultorio o centro médico): turnos, asistencia, cancelaciones, no-shows y facturación, con trazabilidad desde datos hasta KPIs y un recorrido **descriptivo, diagnóstico, predictivo (acotado) y explicativo**.

Los datos son **sintéticos** y **ficticios**; no representan personas, instituciones ni operaciones reales. El propósito es demostrar criterio de **Senior Data Analyst / BI Analyst**: modelado, **gobernanza de métricas**, visualización por rol, lectura de **riesgo operativo** y **ML como capa predictiva complementaria** (ver [`ml/README.md`](../ml/README.md)), sin vender resultados sintéticos como hallazgos reales.

## Problema de negocio

Los centros ambulatorios pierden eficiencia e ingresos por:

- **Huecos de agenda** y baja utilización de franjas.
- **No-shows** (paciente no asiste sin cancelar a tiempo).
- **Cancelaciones**, en particular **tardías**, que impiden reasignar el cupo.
- **Desalineación** entre volumen de citas, atención efectiva y **facturación** (conciliación atención vs cobro).

Sin definiciones estables de métricas y un modelo de datos explícito, los tableros se vuelven difíciles de auditar y comparar en el tiempo; **con solo el histórico no alcanza** para **priorizar** ni para explicitar **señales accionables** sin un diseño analítico explícito.

## Solución analítica (producto del repo)

- **Capa de datos** gobernada: modelo dimensional, datos procesados y reglas de calidad.
- **SQL** como contrato de verdad para KPIs.
- **Power BI** como **vista ejecutiva / monitoreo** (qué pasa y qué mirar).
- **Tableau** como **vista analítica / diagnóstico** (cortes, patrones y causa).
- **Python** para ingesta, calidad y pipeline reproducible.
- **Machine Learning** como **capa predictiva complementaria** (riesgo de no-show) para **priorización** y lectura con **explicabilidad** documentada; no sustituye reglas de negocio ni juicio operativo.

## Stakeholders (roles)

| Rol | Necesidad principal |
|-----|---------------------|
| Dirección / operaciones | KPIs de utilización, ausentismo, tendencias |
| Recepción / agenda | Desglose por canal, franja, reducción de no-shows |
| Facturación / administración | Conciliación citas atendidas vs cargos |
| Jefes de servicio / médicos (secundario) | Carga operativa por especialidad (métricas operativas, no calidad clínica) |
| Data / BI | Modelo documentado, reproducibilidad, linaje |

## Preguntas de negocio guía

### Preguntas troncales (eje analítico T1–T6)

Estas seis preguntas ordenan el marco del repo; la trazabilidad hacia KPIs, SQL, BI y posibles acciones está en [`analytical_questions.md`](analytical_questions.md).

| Id | Pregunta |
|----|----------|
| **T1** | ¿Cómo evolucionan en el tiempo **no-show**, **cancelación**, **citas atendidas** y el volumen operativo agregado? |
| **T2** | ¿**Dónde** se concentra la fricción por **especialidad**, **canal de reserva** y **tiempo** (día, franja)? |
| **T3** | ¿Dónde se concentran las **cancelaciones tardías** (menos de 24 h antes del turno) y en qué combinaciones canal–servicio? |
| **T4** | ¿Cómo evoluciona el **ingreso facturado** y cómo se relaciona con citas **atendidas** en la ventana analizada? |
| **T5** | ¿Qué **brechas** hay entre **citas atendidas** y **líneas de facturación** (conciliación)? |
| **T6** | Ante **riesgo de no-show** en el punto de decisión documentado, **qué citas** priorizar para contacto o seguimiento? |

### Preguntas complementarias

**Descriptivas y de seguimiento**

- ¿Cómo evolucionan **ocupación** (proxy), **no-show** y **cancelación** por especialidad y canal? (Alineada a **T1**–**T2**; la ocupación proxy está en [`metric_definitions.md`](metric_definitions.md) y no en una vista SQL dedicada aún.)
- ¿Cuál es el **ingreso facturado** en el tiempo y cómo se relaciona con citas **atendidas**? (**T4**)
- ¿Qué brechas hay entre **atención** y **facturación**? (**T5**)

**Diagnósticas y orientadas a decisión**

- ¿Qué factores o cortes **parecen asociarse** con mayor ausentismo o fricción (especialidad, franja, canal)? (**T2**)
- ¿Qué **franjas horarias** o combinaciones canal–servicio muestran mayor **volatilidad operativa**? (**T2**–**T3**)
- ¿Qué **perfiles o segmentos** (p. ej. por historial agregado) muestran diferencias relevantes para la agenda? (**T2**, y capa ML **T6** donde aplique)
- ¿Qué **señales** justificarían acciones preventivas (recordatorios, revisión de cupos, monitoreo focalizado)? (Cruce **T1**–**T3** con **T6**)

*Las respuestas sobre datos sintéticos son **ilustrativas**; el valor está en la **metodología** y las definiciones.*

## Alcance MVP (decisiones cerradas)

| Tema | Decisión MVP |
|------|----------------|
| Sedes | **Una sede** (sin `dim_location`); multi-sede queda fuera del MVP. |
| Grano de facturación | **Línea de cargo** en `fact_billing_line`. |
| No-show vs cancelación | Estados **mutuamente excluyentes** en catálogo; cancelación con `cancellation_date` cuando aplica. |
| Ingreso cobrado | **Fuera del MVP** como métrica financiera estricta; opcionalmente **proxy** por estado de línea en fases posteriores. |
| Ocupación | **Proxy** (sin catálogo de slots): capacidad teórica por regla documentada en `metric_definitions.md`. |

## Fuera de alcance (fases posteriores)

- Modelo fino de **capacidad por slot** y reprogramaciones encadenadas.
- **Cobranza** (caja/banco) explícita y conciliación de tesorería.
- Múltiples sedes con gobernanza territorial.

## Ética y uso de métricas por profesional

Las métricas por profesional se entienden como **operativas** (volumen, franja), no como evaluación de desempeño clínico. Los datos son ficticios.
