# Power BI — tablero ejecutivo (diseño v2)

**Estado:** **implementación asistida** — CSV exportados + DAX + instrucciones de lienzo; el archivo `.pbix` se construye en **Power BI Desktop** (binario no versionado por defecto).

**Rol:** seguimiento para **dirección / operación** — “qué pasó en el periodo” y “dónde mirar primero”, sin sustituir el análisis profundo (reservado a Tableau: [`bi/tableau/README.md`](../tableau/README.md)).

**Fuentes de verdad:** [`docs/metric_definitions.md`](../../docs/metric_definitions.md), vistas en [`sql/views/`](../../sql/views/), datos en `data/processed/paradigm_mart.db` tras [`scripts/build_sqlite_mart.py`](../../scripts/build_sqlite_mart.py) y calidad en [`scripts/run_data_quality.py`](../../scripts/run_data_quality.py).

**Preguntas troncales (T1–T6) y trazabilidad a KPIs y artefactos:** [`docs/analytical_questions.md`](../../docs/analytical_questions.md).

---

## 1. Alcance exacto del dashboard ejecutivo (MVP)

| Incluido | Excluido (fuera de este tablero / fase posterior) |
|----------|---------------------------------------------------|
| KPIs operativos con **fecha del turno** como eje principal | **Ocupación proxy** (sin vista SQL dedicada; no forzar card engañosa) |
| Tasas **no-show** y **cancelación** alineadas al diccionario | **Late cancellation rate** (requiere lógica temporal fina; mejor en Tableau o vista futura) |
| Volumen **citas atendidas** | **Ingreso cobrado** real (no hay fecha de cobro en MVP) |
| **Ingreso facturado** con anclaje **`billing_date`** (separado del operativo) | Cualquier KPI no listado en `metric_definitions.md` |
| Indicador de **brecha** atención–facturación (conteo / alerta suave) | **ML / scoring** en este lienzo (modelo aparte: [`ml/README.md`](../../ml/README.md)) |

**Un archivo PBIX, una página principal** (“Ejecutivo”) en el MVP; una segunda página opcional (“Referencia”) solo si hace falta leyendas largas — priorizar **una pantalla** legible en 30–60 s.

---

## 2. Estructura del tablero — páginas y secciones

### Página única recomendada: **Ejecutivo**

| Sección | Objetivo | Lectura esperada |
|---------|----------|-------------------|
| **A — Barra de filtros** | Acotar periodo y cortes de negocio | Misma interpretación que en el diccionario de métricas |
| **B — KPIs (tarjetas)** | Números clave del periodo seleccionado | 4–6 tarjetas máximo |
| **C — Tendencia temporal** | Evolución de volumen o tasas (agenda) | Una línea o área; granularidad semanal o mensual |
| **D — Desglose** | Comparar **especialidad** o **proveedor** (uno a la vez o dos visuales pequeños) | Barras horizontales ordenadas |
| **E — Alerta operativa** | Brechas de facturación en citas atendidas | Una tarjeta o tabla corta |

**Objetivo de cada bloque:** B responde “cuánto”; C “cómo viene en el tiempo” (solo **agenda**); D “dónde”; E “qué revisar en administración”.

---

## 3. KPIs, visuales y fuentes SQL

### 3.1 Principio de modelado en Power BI

- **Operación (agenda):** anclaje **`appointment_date`** (y columnas derivadas en `vw_appointment_base`).
- **Facturación:** anclaje **`billing_date`** en `fact_billing_line` — **no** mezclar con `appointment_date` en el mismo visual salvo que el diseño lo diga explícitamente (ver §5).

**Tabla principal recomendada para filtros y medidas operativas:** **`vw_appointment_base`** (grano cita; ya incluye `specialty_name`, `provider_label`, `channel_code`, `status_code`, fechas de rol).

**Tabla de hecho facturación:** **`fact_billing_line`** relacionada con `vw_appointment_base` por `appointment_id` (relación 1:N desde cita a líneas).

**Vistas preagregadas:** usar como apoyo para **reducir DAX** en gráficos mensuales, no como única fuente si los filtros no aplican (ver §3.3).

### 3.2 Matriz KPI → visual → fuente → anclaje temporal

| KPI (diccionario) | Visual sugerido | Fuente preferida | Anclaje temporal |
|---------------------|-----------------|-------------------|------------------|
| Citas totales (denominador operativo) | Tarjeta | `vw_appointment_base` — `COUNTROWS` / conteo filas | **Fecha del turno** `appointment_date` |
| Citas atendidas | Tarjeta | `vw_appointment_base` — filtro `status_code = "ATTENDED"` | **Fecha del turno** |
| No-show rate | Tarjeta (%) | Medida sobre `vw_appointment_base`: no-show / (atendidas + no-show) | **Fecha del turno** |
| Tasa de cancelación (sobre agenda del periodo) | Tarjeta (%) | Misma base: canceladas / todas las citas con turno en periodo | **Fecha del turno** |
| Ingreso facturado | Tarjeta (importe) | `fact_billing_line` — suma `line_amount` donde estado ≠ VOID | **`billing_date`** |
| Brechas conciliación (conteo atendidas sin facturación) | Tarjeta o tabla corta | `vw_revenue_bridge` — filtrar `reconciliation_bucket = "ATTENDED_NO_BILLING"` | Cita / bucket (operativo); montos vienen de líneas si existieran |
| Tendencia volumen (atendidas o citas totales) | Línea o área | **`vw_daily_kpis`** (solo si el eje es tiempo **sin** necesidad de filtrar por especialidad en el mismo gráfico) **o** medida en `vw_appointment_base` agrupada por `appointment_date` | **Fecha del turno** |
| Desglose por especialidad | Barras horizontales | **`vw_kpis_by_specialty`** para columnas predefinidas **o** medidas en `vw_appointment_base` agrupadas por `specialty_name` | Operativo: **mes del turno** (`year_month` en la vista); ingreso en esa vista usa mes alineado según [`sql/README.md`](../../sql/README.md) |
| Desglose por proveedor | Barras horizontales | **`vw_kpis_by_provider`** o medidas sobre `vw_appointment_base` por `provider_label` | Igual que especialidad |

### 3.3 Limitaciones de las vistas actuales (importante)

| Vista | Uso en ejecutivo | Limitación |
|-------|------------------|------------|
| `vw_daily_kpis` | Tendencia diaria de tasas y conteos | **No tiene** especialidad, proveedor ni canal. Si el usuario filtra por especialidad en la barra, este gráfico **no** debe seguir mostrando la serie global sin aclaración: **preferir** tendencia calculada desde `vw_appointment_base` con los mismos filtros, o ocultar la tendencia cuando hay filtros de dimensión. |
| `vw_kpis_by_specialty` / `vw_kpis_by_provider` | Barras mensuales | Pre-agregadas por `year_month` + dimensión. El **ingreso** en la vista sigue el **mes de facturación** unido al mismo `year_month` del mes del turno (ver `sql/README.md`); puede haber **desalineación** mes turno vs mes factura. Etiquetar el visual de ingreso. |
| `vw_revenue_bridge` | Alerta brecha | Grano cita; adecuado para **conteos** por `reconciliation_bucket`. |
| Ocupación proxy | — | **No hay vista SQL**; no mostrar como KPI numérico en MVP o mostrar texto “no disponible en mart”. |

**No se requieren nuevas vistas SQL** para el ejecutivo MVP si se importan `vw_appointment_base` + `fact_billing_line` y se aceptan las notas anteriores. Si se quisiera **una sola** tendencia filtrable por especialidad sin DAX complejo, una **vista futura** opcional sería `vw_daily_kpis_by_specialty` — **fuera del alcance de esta iteración de diseño**.

---

## 4. Medidas conceptuales (lógica de negocio, sin DAX)

Power BI debería definir medidas con estos **nombres y significados** (implementación en DAX en una fase posterior):

| Medida conceptual | Dependencias / lógica | Notas |
|-------------------|------------------------|-------|
| `Citas Total` | Filas en `vw_appointment_base` en contexto de filtro | Anclaje: `appointment_date` |
| `Citas Atendidas` | `status_code = "ATTENDED"` | Idem |
| `Citas Canceladas` | `status_code = "CANCELLED"` | Idem |
| `Citas No Show` | `status_code = "NO_SHOW"` | Idem |
| `No Show Rate` | `[Citas No Show] / ([Citas Atendidas] + [Citas No Show])` | Denominador cero → en blanco |
| `Tasa Cancelación` | `[Citas Canceladas] / [Citas Total]` | Sobre citas con turno en periodo |
| `Ingreso Facturado` | Suma `line_amount` en `fact_billing_line` con `billing_status` ≠ VOID | Filtrar por **`billing_date`** en el periodo (tabla de fechas de facturación o medida con `USERELATIONSHIP` si se modelan dos roles de fecha) |
| `Citas Atendidas Sin Facturación` | `COUNTROWS` en `vw_revenue_bridge` donde bucket = `ATTENDED_NO_BILLING` | Solo lectura operativa |

**Relaciones de fecha:** se recomienda **calendario** (`dim_date`) con relación activa a `vw_appointment_base[appointment_date]` y relación **inactiva** o calendario duplicado “Billing” a `fact_billing_line[billing_date]` para no mezclar anclajes en un mismo eje por error.

---

## 5. Filtros y navegación

### Filtros globales (segmentadores / slicers)

| Filtro | Campo sugerido | Origen |
|--------|----------------|--------|
| Periodo (agenda) | `appointment_date` o `dim_date` | Rango de fechas del **turno** |
| Especialidad | `specialty_name` | `vw_appointment_base` |
| Proveedor | `provider_label` | `vw_appointment_base` |
| Canal de reserva | `channel_code` o `booking_channel_name` | `vw_appointment_base` |
| Estado de cita | `status_code` | **Opcional** en ejecutivo (al filtrar “solo atendidas” se alteran tasas); usar con tooltip de ayuda |

**Periodo de facturación:** si se muestra ingreso facturado, usar **slicer separado** sobre `billing_date` o un conmutador claro “Agenda vs Facturación” para evitar confusiones.

**Navegación:** MVP sin botones de bookmarks; un solo lienzo.

---

## 6. Riesgos y notas metodológicas

| Tema | Acción en el tablero |
|------|----------------------|
| Operativo vs facturación | Etiquetar tarjetas: “Agenda (fecha turno)” vs “Facturación (fecha emisión)” |
| `revenue_facturado_mes` en vistas mensuales | Texto corto en tooltip: posible desfase turno vs factura |
| Calidad de datos | Tras `run_data_quality.py`, un **WARN** por atendidas sin línea es **esperado**; la tarjeta de brecha lo refuerza |
| Rankings por proveedor | Recordatorio en pie de página: métricas **operativas**, no calidad clínica ([`docs/business_case.md`](../../docs/business_case.md)) |
| SQLite local | Conector actualizado; rutas relativas si se mueve el repo |

---

## 7. Fuente de datos implementada (MVP)

**Decisión:** export **CSV** desde el mismo mart SQLite que las vistas SQL, para máxima portabilidad y sin depender del conector SQLite en el equipo donde se diseña el informe.

| Origen en el mart | Archivo CSV en `source_csv/` | Uso en Power BI |
|-------------------|-------------------------------|-----------------|
| `vw_appointment_base` | `AppointmentBase.csv` | Hecho operativo, filtros, tendencia, desglose |
| `fact_billing_line` + `dim_billing_status` | `BillingLine.csv`, `DimBillingStatus.csv` | Ingreso facturado (excluye VOID vía relación + medida) |
| `dim_date` | `DimDate.csv` | Eje temporal de agenda (opcional) |
| `vw_revenue_bridge` | `RevenueBridge.csv` | Medida de brecha (`ATTENDED_NO_BILLING`) |
| `vw_daily_kpis`, `vw_kpis_by_specialty` | `DailyKpis.csv`, `KpiBySpecialty.csv` | Opcional / referencia (el lienzo MVP prioriza medidas sobre `AppointmentBase`) |

**Generación:**

```bash
python scripts/build_sqlite_mart.py
python scripts/export_powerbi_source.py
```

Salida: [`source_csv/`](source_csv/).

---

## 8. Qué quedó construido en el repo (vs manual en Power BI)

| Artefacto | Ubicación |
|-----------|-----------|
| CSV listos para importar | `bi/powerbi/source_csv/*.csv` |
| Medidas DAX | [`dax/executive_measures.dax`](dax/executive_measures.dax) |
| Pasos de modelo y lienzo | [`BUILD_INSTRUCTIONS.md`](BUILD_INSTRUCTIONS.md) |
| Referencia numérica (validación) | `python scripts/validate_executive_kpis.py` |

**Manual obligatorio:** crear el archivo `.pbix` en Power BI Desktop importando los CSV, relaciones, medidas y visuales según `BUILD_INSTRUCTIONS.md`.

---

## 9. KPIs incluidos en las medidas (MVP)

Alineados a [`docs/metric_definitions.md`](../../docs/metric_definitions.md):

| Medida | Tipo |
|--------|------|
| `Citas Total` | Operativo (fecha turno) |
| `Citas Atendidas` / `Citas Canceladas` / `Citas No Show` | Operativo |
| `No Show Rate` | Operativo |
| `Tasa Cancelacion` | Operativo |
| `Ingreso Facturado` | Facturación (`billing_date` en segmentador; ver interacciones en BUILD_INSTRUCTIONS) |
| `Citas Atendidas Sin Facturacion` | Conciliación (coherente con `vw_revenue_bridge`) |

**Fuera de alcance:** ocupación proxy, late cancel, ingreso cobrado real, ML.

---

## 10. Validación frente al mart y al quality report

Ejecutar:

```bash
python scripts/validate_executive_kpis.py
```

**Referencia actual (dataset sintético sin filtros de fecha):** citas totales **520**, atendidas **368**, no-show rate **0,1300**, tasa cancelación **0,1865**, ingreso facturado total **6.904.253,48** ARS, brechas **31** (coincide con WARN del reporte de calidad y con `vw_revenue_bridge`).

**Inconsistencias conocidas (no expandir alcance sin decisión):**

- Si los segmentadores de **agenda** filtran la tarjeta de **Ingreso facturado**, el total puede diferir del SQL global — por eso se recomienda **editar interacciones** o un segmentador dedicado a `billing_date` (§4 de `BUILD_INSTRUCTIONS.md`).
- `DailyKpis` importada no se usa obligatoriamente en el MVP; la tendencia se basa en `AppointmentBase` para respetar filtros de especialidad.

---

## 11. Limitaciones que mantiene esta fase

- Sin archivo `.pbix` en el repositorio (opcional añadirlo localmente; puede ignorarse en Git por tamaño).
- Conexión **directa** al `.db` no es obligatoria si se usan CSV regenerables.
- Tableau y ML: fuera de alcance.

---

## 12. Evidencia para el README raíz

Cuando el `.pbix` esté armado:

1. Captura del lienzo **Ejecutivo** → guardar como [`assets/powerbi-executive.png`](../../assets/) (nombre sugerido).
2. En el README raíz (sección v2), una línea: *Tablero ejecutivo implementado en Power BI Desktop; fuente CSV + medidas en `bi/powerbi/`.*

**No incluir** aún capturas Tableau ni ML.
