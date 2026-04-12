# Paradigm v2 — Diccionario de métricas (KPIs)

**Principios**

- Cada KPI declara **fecha de anclaje** (fecha del turno vs fecha de facturación vs fecha de cancelación).
- Definiciones del **MVP**; métricas marcadas “fase posterior” no son obligatorias en el primer tablero.
- Nombres de tabla alineados a `data_dictionary.md` y al modelo dimensional del plan.

## Anclaje temporal por KPI

| KPI | Fecha principal | Nota |
|-----|-----------------|------|
| Ocupación (proxy) | Fecha del turno | Denominador por regla proxy (sin slots en MVP). |
| No-show rate | Fecha del turno | Denominador: atendidas + no-shows (citas que debían ocurrir). |
| Cancelación rate | Fecha de cancelación o fecha de turno | Documentar vista; dos preguntas distintas. |
| Late cancellation rate | Derivada de fechas/horas | Umbral MVP: **&lt; 24 h** antes del inicio del turno. |
| Citas atendidas | Fecha del turno | Estado = atendida. |
| Ingreso facturado | Fecha de facturación (`billing_date`) | No usar fecha de turno para P&L de facturación. |
| Ingreso cobrado | — | **Fase posterior** (sin fecha de cobro en MVP). |
| Ingreso por cita atendida | Alineación explícita | **Opción adoptada en MVP:** ingreso por líneas cuyo `billing_date` cae en el periodo y cita atendida en el mismo universo analítico (ver reglas). |
| Conciliación | Cruz cita–líneas | Por fila de cita atendida. |
| Productividad por profesional / especialidad | Fecha del turno | Especialidad = `specialty_id` en cita. |

---

## 1. Ocupación de agenda (proxy)

| Campo | Contenido |
|-------|-----------|
| **Definición** | Proporción de **citas que consumen cupo operativo** respecto de una **capacidad teórica** por proveedor y día. |
| **Numerador** | Citas con estado **no cancelado** cuya fecha de turno cae en el periodo y en días/horas de atención (excluir canceladas). |
| **Denominador** | **Capacidad proxy:** `cupos_teoricos_por_proveedor_día` (constante documentada, p. ej. 16 citas/día por proveedor en MVP). |
| **Fuente** | `fact_appointment`, `dim_appointment_status`, `dim_date` (fecha turno). |
| **Limitación** | Sin modelo de **slots** ni duración real; el KPI es **ilustrativo** y debe etiquetarse como proxy en narrativas públicas. |

## 2. No-show rate

| Campo | Contenido |
|-------|-----------|
| **Definición** | Proporción de no-shows sobre citas que **debían realizarse** (excluye canceladas). |
| **Numerador** | Cuenta de citas con estado **no-show**. |
| **Denominador** | Cuenta de citas **atendidas + no-show** en el periodo (misma fecha de turno). |
| **Fuente** | `fact_appointment`, `dim_appointment_status`. |

## 3. Cancelación rate

| Campo | Contenido |
|-------|-----------|
| **Definición** | Proporción de citas **canceladas** sobre un universo explícito. |
| **Variante MVP — sobre agenda del mes** | Numerador: canceladas con fecha de turno en el periodo. Denominador: todas las citas con fecha de turno en el periodo. |
| **Fuente** | `fact_appointment`, fechas de turno y cancelación. |

## 4. Late cancellation rate

| Campo | Contenido |
|-------|-----------|
| **Definición** | Entre citas canceladas, proporción donde la cancelación ocurre **menos de 24 horas** antes del `appointment_start` (datetime). |
| **Numerador** | Canceladas tardías. |
| **Denominador** | Total **canceladas** (recomendado en MVP). |
| **Fuente** | `fact_appointment` con `cancellation_ts` y `appointment_start`. |

## 5. Citas atendidas

| Campo | Contenido |
|-------|-----------|
| **Definición** | Recuento de citas con estado **atendida**. |
| **Fuente** | `fact_appointment`. |

## 6. Ingreso facturado

| Campo | Contenido |
|-------|-----------|
| **Definición** | Suma de `line_amount` en líneas con estado distinto de **anulado** y `billing_date` en el periodo. |
| **Fuente** | `fact_billing_line`, `dim_billing_status`. |

## 7. Ingreso cobrado

| Campo | Contenido |
|-------|-----------|
| **Estado** | **No publicado en MVP** como métrica financiera de cobranza real (no hay fecha de pago). |
| **Nota** | Si en el futuro se usa `PAID` como proxy, documentar como **proxy de cobro**. |

## 8. Ingreso por cita atendida

| Campo | Contenido |
|-------|-----------|
| **Definición** | Ingreso facturado asociado a citas atendidas / número de citas atendidas en la ventana analizada. |
| **Regla MVP** | Sumar líneas válidas ligadas a citas **atendidas**; excluir líneas anuladas. |

## 9. Conciliación atención vs facturación

| Campo | Contenido |
|-------|-----------|
| **Definición** | Por cada cita atendida: presencia de línea(s) **emitida/pagada** vs **pendiente** vs **sin línea**. |
| **Fuente** | Join `fact_appointment` ↔ `fact_billing_line`. |

## 10. Productividad operativa por profesional

| Campo | Contenido |
|-------|-----------|
| **Definición** | Citas atendidas por `provider_id` y periodo (por día o semana). |
| **Ética** | Métrica **operativa**, no evaluación clínica. |

## 11. Productividad por especialidad

| Campo | Contenido |
|-------|-----------|
| **Definición** | Citas atendidas agrupadas por `specialty_id` de la **cita** (no por especialidad principal del médico sola). |

## 12. Distribución por canal de reserva

| Campo | Contenido |
|-------|-----------|
| **Definición** | Participación de canales en volumen de citas (por `booking_date` o `appointment_date` según la pregunta). |

---

## Reglas globales MVP

- **Moneda:** ARS; un solo tipo de moneda en datos sintéticos.
- **Estados de cita:** mutuamente excluyentes (atendida / cancelada / no-show).
- **Ingreso facturado:** anclado a **`billing_date`**, no a la fecha del turno.
