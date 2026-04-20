# SQL — Paradigm v2 (SQLite local)

## Por qué SQLite

- **Portabilidad:** un solo archivo (`data/processed/paradigm_mart.db`) clonable sin servidor.
- **Portfolio:** demuestra DDL, vistas y consultas reproducibles en cualquier máquina con Python.
- **Alcance:** capa analítica **local** alineada al modelo del plan; Power BI / Tableau pueden conectar al `.db` o exportar CSV desde vistas.

**Limitación:** no es un motor para producción concurrente; basta para MVP y demos.

## Cómo crear la base y cargar datos

1. Tener generados los CSV en [`data/synthetic/`](../data/synthetic/README.md):

   ```bash
   python scripts/generate_paradigm_v2_synthetic.py
   ```

2. Ejecutar el build (DDL + carga + vistas):

   ```bash
   python scripts/build_sqlite_mart.py
   ```

3. (Recomendado) Validar calidad del mart y generar reporte:

   ```bash
   python scripts/run_data_quality.py
   ```

   Salida: `reports/quality_report.md` — ver [`python/README.md`](../python/README.md).

Salida del paso 2: **`data/processed/paradigm_mart.db`** (regenera el archivo si ya existía).

Requisitos: Python 3.10+ con `pandas` (ver [`requirements.txt`](../requirements.txt)).

## Esquema (DDL)

Definido en [`ddl/01_create_tables.sql`](ddl/01_create_tables.sql):

- Dimensiones: `dim_date`, `dim_specialty`, `dim_coverage`, `dim_appointment_status`, `dim_booking_channel`, `dim_billing_status`, `dim_cancellation_reason`, `dim_patient`, `dim_provider`.
- Hechos: `fact_appointment`, `fact_billing_line`.

Claves foráneas activadas (`PRAGMA foreign_keys = ON` en el script de build).

## Vistas analíticas

| Vista | Propósito |
|-------|-----------|
| `vw_appointment_base` | Citas enriquecidas con dimensiones y `appointment_date_key` / `booking_date_key` / `cancellation_date_key`. |
| `vw_daily_kpis` | KPIs por **fecha del turno**: totales, atendidas, canceladas, no-shows, tasas (definiciones en `docs/metric_definitions.md`). |
| `vw_kpis_by_specialty` | Agregado **mensual** por especialidad operativa; incluye `revenue_facturado_mes` con **mes de facturación** (`billing_date`) alineado al mismo `year_month` que el mes del turno (ver nota abajo). |
| `vw_kpis_by_provider` | Igual por proveedor. |
| `vw_revenue_bridge` | Por **cita**: montos por tipo de estado de facturación y `reconciliation_bucket` (p. ej. `ATTENDED_NO_BILLING`). |

### Nota sobre ingreso en vistas por especialidad / proveedor

`revenue_facturado_mes` se calcula con **`strftime('%Y-%m', billing_date)`** y especialidad/proveedor desde la cita. El join con los KPIs operativos (basados en **`appointment_date`**) usa el **mismo etiquetado `year_month`**: en la práctica, ingreso y turnos quedan alineados cuando facturación y turno caen en el mismo mes calendario; si una línea se factura en un mes distinto al del turno, el efecto queda repartido entre meses de **billing** (comportamiento esperado para ingreso facturado).

## Consultas de ejemplo

En [`samples/`](samples/):

| Archivo | Tema |
|---------|------|
| `01_no_show_by_specialty.sql` | No-show por especialidad |
| `02_cancellation_by_channel.sql` | Cancelación por canal |
| `03_attended_by_month.sql` | Citas atendidas por mes |
| `04_billing_by_month.sql` | Facturación por mes (`billing_date`) |
| `05_reconciliation_attendance_vs_billing.sql` | Conciliación vía `vw_revenue_bridge` |

Ejecutar con la CLI de SQLite (si está instalada):

```bash
sqlite3 data/processed/paradigm_mart.db < sql/samples/01_no_show_by_specialty.sql
```

O desde cualquier cliente SQL apuntando al archivo `.db`.

## Limitaciones de esta fase

- Sin **stored procedures** ni jobs: la “carga” es el script Python.
- **Ingreso cobrado** real no modelado (solo estados de línea; `PAID` es proxy según diccionario).
- **Ocupación proxy** no materializada en vista aún (pendiente regla de capacidad por proveedor/día en SQL o BI).
- Vistas **no** sustituyen el diccionario de métricas: siempre validar definiciones en [`docs/metric_definitions.md`](../docs/metric_definitions.md).
