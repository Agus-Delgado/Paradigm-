# Tableau — capa analítica / exploratoria (Paradigm v2)

**Estado:** **diseño e implementación asistida** — fuentes CSV desde el mart SQLite + especificación de libro/historias; el `.twbx` se arma en **Tableau Desktop** (binario no versionado por defecto).

**Rol:** **exploración, comparación de segmentos y lectura de causa** (“por qué” y “dónde profundizar”), no el resumen ejecutivo de una pantalla. Complementa al tablero de Power BI documentado en [`../powerbi/README.md`](../powerbi/README.md).

**Fuentes de verdad:** [`docs/metric_definitions.md`](../../docs/metric_definitions.md), vistas en [`sql/views/`](../../sql/views/), mart en `data/processed/paradigm_mart.db` tras [`scripts/build_sqlite_mart.py`](../../scripts/build_sqlite_mart.py), calidad en [`scripts/run_data_quality.py`](../../scripts/run_data_quality.py).

**Fuera de alcance de este lienzo:** modelos ML en Tableau (el scoring vive en [`ml/README.md`](../../ml/README.md)); ocupación proxy como KPI numérico; ingreso cobrado como métrica financiera estricta; **cualquier métrica no listada** en el diccionario.

---

## 1. Alcance del dashboard analítico (vs Power BI ejecutivo)

| Dimensión | Power BI (ejecutivo) | Tableau (esta capa) |
|-----------|----------------------|---------------------|
| Pregunta principal | “¿Qué pasó en el periodo y qué número resume la operación?” | “¿Qué segmentos explican el comportamiento y cómo se combinan tiempo, canal y especialidad?” |
| Granularidad | Mensual / diario para tendencia global; pocas tarjetas | **Grano cita** y cortes múltiples simultáneos; tablas y matrices densas |
| Tiempo | Un eje principal claro (fecha de turno para operación; facturación aparte) | **Varios anclajes** explícitos en el mismo libro (turno vs facturación vs cancelación) |
| Visual típico | KPI cards, una tendencia, barras de desglose | Scatter, heatmap, barras apiladas por causa, **parámetros** de umbral y drill |
| Duplicación | — | **No** repetir la “página única ejecutiva” (mismas 4–6 tarjetas y mismo relato); usar Tableau para **preguntas adicionales** listadas abajo |

**Preguntas que Tableau debe responder (prioridad):**

1. **Root cause operativo:** ¿Qué combinación de **especialidad × canal × día de la semana** (o mes) concentra no-shows o cancelaciones?
2. **Comparación de segmentos:** ¿Cómo se ordenan especialidades y canales en **tasa** y en **volumen** (dos lecturas distintas)?
3. **Cancelación:** ¿Cuál es el perfil por **motivo de cancelación** (donde exista dato) y cómo difiere la **cancelación temprana vs tardía** (late cancellation, menos de 24 h antes del turno)?
4. **Facturación vs agenda:** ¿Dónde hay **brechas** de conciliación (puente atención–facturación) y si se concentran en ciertos cortes?
5. **Temporal:** tendencias **diarias o semanales** con filtros de dimensión **sin** perder coherencia (misma lógica que en el diccionario).

**Qué dejar en Power BI y no “re-ejecutar” como narrativa principal en Tableau:** la misma fila de KPIs globales del periodo y la misma historia de “una pantalla en 30–60 s”. En Tableau pueden existir **referencias** a esas métricas como verificación cruzada, no como dashboard gemelo.

---

## 2. Fuentes de datos

### 2.1 Recomendación (simplicidad + consistencia con el mart)

| Archivo CSV (salida script) | Origen SQL | Uso principal en Tableau |
|-----------------------------|------------|---------------------------|
| `AppointmentBase.csv` | `vw_appointment_base` | **Hecho principal (grano cita):** estados, especialidad, canal, fechas de rol, `appointment_iso_week`, `appointment_day_of_week`, motivo cancelación |
| `BillingLine.csv` | `fact_billing_line` | Ingreso facturado con **`billing_date`**; relación a cita por `appointment_id` |
| `DimDate.csv` | `dim_date` | Calendario para jerarquías y semana ISO si se relaciona por `appointment_date_key` / claves equivalentes |
| `DimBillingStatus.csv` | `dim_billing_status` | Etiquetas de estado de línea |
| `DailyKpis.csv` | `vw_daily_kpis` | Serie **diaria** global (tasas ya definidas en SQL); **sin** especialidad/canal — solo como apoyo o vista “total mercado” |
| `KpiBySpecialty.csv` | `vw_kpis_by_specialty` | Serie **mensual** por especialidad (operativo + `revenue_facturado_mes` con nota de alineación) |
| `KpiByProvider.csv` | `vw_kpis_by_provider` | Serie **mensual** por proveedor (misma advertencia de ingreso que por especialidad) |
| `RevenueBridge.csv` | `vw_revenue_bridge` | Conciliación por cita: buckets y montos agregados por cita |

**Conexión recomendada en Tableau:** modelo **relacional**: `AppointmentBase` como centro; **LEFT** join a `BillingLine` por `appointment_id` (1:N); `DimDate` relacionado por `appointment_date_key` a `appointment_date`/`DimDate.date_key` según convenga; `RevenueBridge` opcional por `appointment_id` si se quiere evitar duplicar lógica de bucket.

**No hace falta** un esquema distinto al mart: las mismas entidades que ya validan el quality report.

### 2.2 Export CSV para Tableau

Desde la raíz del repo:

```text
python scripts/build_sqlite_mart.py
python scripts/export_tableau_source.py
```

Salida: `bi/tableau/source_csv/`. Codificación **UTF-8 con BOM** (`utf-8-sig`) para Excel/Tableau en Windows.

**¿Un export “especial” solo para Tableau?** Sí, en el sentido de **carpeta y script dedicados** (`export_tableau_source.py`) que incluyen **`KpiByProvider`**, útil para análisis por profesional sin recalcular todo desde el grano cita. **No** se introduce una métrica nueva: es la vista SQL ya definida.

Si en el futuro se necesita **una sola tabla ultra-plana** (todas las dimensiones en una fila por línea de facturación), convendría una **vista SQL** `vw_billing_line_enriched` en el mart y entonces sumarla al export; **no es obligatoria** para el MVP analítico descrito aquí.

---

## 3. Estructura sugerida del libro (o historia)

Convención: varias **hojas** temáticas + filtros globales (periodo, especialidad, canal). Opcional: **Story** con tres pasos “volumen → tasa → causa”.

| Hoja / sección | Objetivo | Visual sugerido |
|----------------|----------|------------------|
| **A — Mapa de calor agenda** | Patrones por **día de semana** y **especialidad** (o canal) | Heatmap: `appointment_day_of_week` × `specialty_name`, color = tasa no-show o % canceladas (con tamaño mínimo de celda por volumen en tooltip) |
| **B — No-show y asistencia** | Evolución y comparación | Líneas temporales (semana/mes) desde **grano cita** o `DailyKpis` para total; barras lado a lado por especialidad |
| **C — Cancelación y motivos** | Volumen y tasa; causa | Barras apiladas o treemap por `cancellation_reason_description` (filtrado a `CANCELLED`); tabla resumen |
| **D — Canales** | Comportamiento por `booking_channel_name` | Barras ordenadas + scatter volumen vs tasa (mismas definiciones que en samples SQL) |
| **E — Late cancellation** | Umbral: menos de 24 h antes del turno | Cálculo en Tableau (ver §4); histograma o barras por franja horas/día |
| **F — Facturación y brecha** | Separar P&amp;L de agenda | Vista con **`billing_date`**; tabla o barras por mes de facturación; **otra** vista con `RevenueBridge` por `reconciliation_bucket` |
| **G — “Cohorte” ligera** | Solo si el dataset lo soporta | **No** cohortes clásicas de retención (faltan reglas de negocio explícitas en el diccionario). **Sustituto MVP:** matriz **mes de reserva** × **mes de turno** (lead time de agenda) usando `booking_date` vs `appointment_date`, color = volumen o % no-show |

**Heatmap:** soportado con `appointment_day_of_week` + dimensión de negocio en `AppointmentBase`.

**Cohortes:** el modelo actual no define cohorte de paciente para KPIs; la matriz mes reserva × mes turno es un **análisis de pipeline de agenda**, no “retención”. Etiquetar como tal.

---

## 4. Cálculos y lógica (conceptual)

Todas las fórmulas deben poder **reconciliarse** con [`docs/metric_definitions.md`](../../docs/metric_definitions.md). Abajo, intención y dependencias; la sintaxis Tableau puede ser `LOD`, `SUM`/`COUNT` según el modelo.

| Tema | Definición (diccionario) | Dependencias / anclaje |
|------|--------------------------|-------------------------|
| **No-show rate** | No-show / (atendidas + no-show) | Solo citas con turno en el periodo; **fecha del turno** `appointment_date` |
| **Cancelación rate (agenda del mes)** | Canceladas / todas las citas con turno en el periodo | **Fecha del turno** |
| **Cancelación vista por fecha de cancelación** | Pregunta distinta: filtrar por `cancellation_date_key` / `cancellation_ts` | **No** mezclar en el mismo visual que la tasa por turno sin subtítulo |
| **Late cancellation rate** | Entre canceladas, % con cancelación menos de 24 h antes de `appointment_start` | Requiere parseo de `cancellation_ts` y `appointment_start`; denominador = canceladas (MVP) |
| **Ingreso facturado** | Suma `line_amount` excluyendo VOID; periodo = **`billing_date`** | Independiente del mes del turno; no comparar ingreso mensual con volumen de turnos del mismo mes **en un solo eje** sin aclarar |
| **Ingreso en vistas `KpiBySpecialty` / `KpiByProvider`** | Ya mezclan mes operativo con ingreso por mes de factura en el join | Usar con **etiqueta** de advertencia (ver [`sql/README.md`](../../sql/README.md)) |

**Relaciones temporales a dejar explícitas en títulos:** “Operación (fecha de turno)” vs “Facturación (fecha de facturación)” vs “Cancelación registrada (fecha/hora de cancelación)”.

---

## 5. Riesgos y límites

| Riesgo | Mitigación |
|--------|------------|
| **Dos definiciones de cancelación** (turno vs momento de cancelación) | Dos hojas o parámetro de “modo de anclaje”; subtítulos fijos |
| **Ingreso mensual en vistas pre-agregadas** vs mes del turno | No usar esas columnas de ingreso en el mismo gráfico que volumen de turnos **sin** nota; preferir `BillingLine` para análisis de facturación |
| **`vw_daily_kpis` sin dimensiones** | No filtrar el gráfico como si respondiera a especialidad/canal |
| **Datos sintéticos** | Evitar inferencia causal; tratar como demo de **método** |
| **Ocupación proxy** | No publicar como KPI numérico (sin slots en mart) |
| **Ingreso cobrado** | No mostrar como cobranza real (ver diccionario) |
| **Evaluación de profesionales** | Productividad operativa solo; no lectura “calidad clínica” |

**Qué no conviene mostrar en Tableau en esta fase:** un tablero que repita la **misma jerarquía de KPIs** que el ejecutivo de Power BI; mapas geográficos sin dimensión geográfica en el mart; cualquier métrica inventada fuera del diccionario.

**Transformaciones extra:** si se desea **hora del día** como eje, hace falta derivar hora desde `appointment_start` en Tableau o en una vista SQL futura; justificar por volumen de análisis (no está en el MVP mínimo).

---

## 6. MVP: límites del entregable

- Libro Tableau **construido manual o semimanual** a partir de `bi/tableau/source_csv/`, siguiendo esta especificación.
- Validación numérica cruzada opcional contra [`scripts/run_data_quality.py`](../../scripts/run_data_quality.py) y totales del mart.
- Sin servidor Tableau obligatorio; Desktop + exportación de imágenes para documentación.

---

## 7. Evidencia recomendada para el README raíz (cuando exista el `.twbx`)

- Captura de **una heatmap** y **una vista de causa/motivo** (sin datos sensibles si aplica).
- Una línea de texto: “Análisis profundo en Tableau; ejecutivo en Power BI” con enlaces a `bi/tableau/README.md` y `bi/powerbi/README.md`.
- Opcional: ruta relativa a `assets/` si el repo guarda thumbnails en [`../../assets/`](../../assets/).

---

## Referencias cruzadas

- Diccionario de métricas: [`docs/metric_definitions.md`](../../docs/metric_definitions.md)
- Notas de vistas SQL: [`sql/README.md`](../../sql/README.md)
- Ejecutivo Power BI: [`../powerbi/README.md`](../powerbi/README.md)
- Muestras de consultas alineadas: [`sql/samples/`](../../sql/samples/)
