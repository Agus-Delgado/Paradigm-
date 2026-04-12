# Paradigm v2 — Caso de negocio

## Resumen

**Paradigm v2** es un proyecto de portfolio que modela una **plataforma analítica end-to-end** para la **operación ambulatoria** de un consultorio o centro médico: turnos, asistencia, cancelaciones, no-shows y facturación, con trazabilidad desde datos hasta KPIs.

Los datos son **sintéticos** y **ficticios**; no representan personas, instituciones ni operaciones reales. Su propósito es demostrar criterio de **Senior Data Analyst / BI Analyst** (modelado, gobernanza de métricas, visualización y **ML acotado** como capa complementaria — ver [`ml/README.md`](../ml/README.md)).

## Problema de negocio

Los centros ambulatorios pierden eficiencia e ingresos por:

- **Huecos de agenda** y baja utilización de franjas.
- **No-shows** (paciente no asiste sin cancelar a tiempo).
- **Cancelaciones**, en particular **tardías**, que impiden reasignar el cupo.
- **Desalineación** entre volumen de citas, atención efectiva y **facturación** (conciliación atención vs cobro).

Sin definiciones estables de métricas y un modelo de datos explícito, los tableros se vuelven difíciles de auditar y comparar en el tiempo.

## Solución analítica (producto del repo)

- **Capa de datos** gobernada: modelo dimensional, datos procesados y reglas de calidad.
- **SQL** como contrato de verdad para KPIs (fases posteriores).
- **Power BI** orientado a **seguimiento ejecutivo** (qué pasa y qué mirar).
- **Tableau** orientado a **análisis y causa raíz** (por qué y dónde profundizar).
- **Python** para ingesta, calidad y pipeline reproducible.
- **Machine Learning** complementario (p. ej. riesgo de no-show), sin sustituir reglas de negocio ni juicio operativo.

## Stakeholders (roles)

| Rol | Necesidad principal |
|-----|---------------------|
| Dirección / operaciones | KPIs de utilización, ausentismo, tendencias |
| Recepción / agenda | Desglose por canal, franja, reducción de no-shows |
| Facturación / administración | Conciliación citas atendidas vs cargos |
| Jefes de servicio / médicos (secundario) | Carga operativa por especialidad (métricas operativas, no calidad clínica) |
| Data / BI | Modelo documentado, reproducibilidad, linaje |

## Preguntas de negocio guía

- ¿Cómo evolucionan **ocupación** (proxy), **no-show** y **cancelación** por especialidad y canal?
- ¿Dónde se concentran **cancelaciones tardías**?
- ¿Cuál es el **ingreso facturado** en el tiempo y cómo se relaciona con citas **atendidas**?
- ¿Qué brechas hay entre **atención** y **facturación** (pendiente, anulado, sin línea)?

## Alcance MVP (decisiones cerradas)

| Tema | Decisión MVP |
|------|----------------|
| Sedes | **Una sede** (sin `dim_location`); multi-sede queda fuera del MVP. |
| Grano de facturación | **Línea de cargo** en `fact_billing`. |
| No-show vs cancelación | Estados **mutuamente excluyentes** en catálogo; cancelación con `cancellation_date` cuando aplica. |
| Ingreso cobrado | **Fuera del MVP** como métrica financiera estricta; opcionalmente **proxy** por estado de línea en fases posteriores. |
| Ocupación | **Proxy** (sin catálogo de slots): capacidad teórica por regla documentada en `metric_definitions.md`. |

## Fuera de alcance (fases posteriores)

- Modelo fino de **capacidad por slot** y reprogramaciones encadenadas.
- **Cobranza** (caja/banco) explícita y conciliación de tesorería.
- Múltiples sedes con gobernanza territorial.

## Ética y uso de métricas por profesional

Las métricas por profesional se entienden como **operativas** (volumen, franja), no como evaluación de desempeño clínico. Los datos son ficticios.
