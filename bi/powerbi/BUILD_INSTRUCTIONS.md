# Construcción del lienzo Power BI (MVP ejecutivo)

Requisitos: **Power BI Desktop** (Windows). Los pasos asumen datos exportados con `python scripts/export_powerbi_source.py`.

## 1. Datos

1. Abrir Power BI Desktop → **Obtener datos** → **Texto/CSV** (o **Carpeta** y seleccionar `bi/powerbi/source_csv/`).
2. Cargar cada archivo con **Transformar datos** y, si hace falta, tipar:
   - `AppointmentBase[appointment_date]` → **Fecha**
   - `BillingLine[billing_date]` → **Fecha**
   - `DimDate[date]` → **Fecha**
3. **Cerrar y aplicar**.

**Nombres de tabla:** renombrar en el panel de campos para que coincidan exactamente con `dax/executive_measures.dax`: `AppointmentBase`, `BillingLine`, `DimBillingStatus`, `DimDate`, `DailyKpis`, `KpiBySpecialty`, `RevenueBridge`.

## 2. Relaciones (Vista de modelo)

| De | A | Cardinalidad |
|----|---|--------------|
| `DimDate[date]` | `AppointmentBase[appointment_date]` | 1:N |
| `AppointmentBase[appointment_id]` | `BillingLine[appointment_id]` | 1:N |
| `DimBillingStatus[billing_status_id]` | `BillingLine[billing_status_id]` | 1:N |
| `AppointmentBase[appointment_id]` | `RevenueBridge[appointment_id]` | 1:1 |

No relacionar `DailyKpis` ni `KpiBySpecialty` con el calendario si se usan como tablas auxiliares; o relacionar `DailyKpis[appointment_date]` con `DimDate[date]` solo si los tipos coinciden (opcional).

## 3. Medidas

Crear las medidas del archivo [`dax/executive_measures.dax`](dax/executive_measures.dax) (pegar una por una en la tabla `AppointmentBase` o en una tabla “Medidas”).

## 4. Interacciones (importante)

- **Tarjeta “Ingreso facturado”:** la métrica es de **facturación** (`billing_date`). Añadir un **segmentador** solo sobre `BillingLine[billing_date]` (rango) para esta métrica.
- En **Formato → Editar interacciones**, desactivar la influencia de los segmentadores de **agenda** (especialidad, proveedor, canal, `DimDate` de turno) sobre la tarjeta de **Ingreso facturado**, para no mezclar anclajes. Los KPIs operativos (citas, tasas) sí deben reaccionar a esos segmentadores.

Alternativa aceptable: dejar interacciones por defecto sabiendo que el ingreso queda filtrado por las citas visibles (ingreso **asociado a citas filtradas**, no “facturación del mes” puro). Si elegís esto, renombrar la tarjeta a **“Ingreso (líneas de citas filtradas)”**.

## 5. Una página “Ejecutivo”

| Sección | Visual | Campos |
|---------|--------|--------|
| **A Filtros** | Segmentadores | `DimDate` jerarquía o `AppointmentBase[appointment_date]`; `specialty_name`; `provider_label`; `channel_code` |
| **B Tarjetas** | Tarjeta (×5–6) | `[Citas Total]`, `[Citas Atendidas]`, `[No Show Rate]`, `[Tasa Cancelacion]`, `[Ingreso Facturado]`, `[Citas Atendidas Sin Facturacion]` |
| **C Tendencia** | Gráfico de líneas | Eje X: `AppointmentBase[appointment_date]` (por mes); Valor: `[Citas Atendidas]` |
| **D Desglose** | Gráfico de barras horizontales | Eje Y: `specialty_name`; Valor: `[Citas Atendidas]` |
| **E Alerta** | Tabla o tarjeta | `[Citas Atendidas Sin Facturacion]` + texto de ayuda |

Título de página: **Ejecutivo — Agenda (fecha turno) / Facturación (fecha emisión en tarjeta de ingreso)**.

## 6. Guardar

Guardar como `Paradigm_executive.pbix` en `bi/powerbi/` (opcional) o fuera del repo si el archivo es grande.

## 7. Validación numérica

Ejecutar en el repo:

```bash
python scripts/validate_executive_kpis.py
```

Comparar totales sin filtros con las tarjetas del informe (sin segmentadores activos).
