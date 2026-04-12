# Python — Paradigm v2

## Rol en el proyecto

- **`src/paradigm/io/`** — rutas al repositorio y al mart SQLite (`paths.py`).
- **`src/paradigm/quality/`** — checks de calidad sobre la base cargada, generación del reporte Markdown.

No hay transformación pesada `raw → processed` en esta fase: la **fuente analítica** para BI es el SQLite construido desde `data/synthetic/`. La calidad valida ese mart antes de conectar herramientas de visualización.

## Flujo recomendado (reproducible)

Desde la **raíz del repositorio**:

```bash
python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py
python scripts/run_data_quality.py
python scripts/export_powerbi_source.py
python scripts/validate_executive_kpis.py
python scripts/train_no_show.py
```

Para Power BI: importar CSV desde `bi/powerbi/source_csv/` (ver [`bi/powerbi/README.md`](../bi/powerbi/README.md)). Modelo de no-show (opcional): artefactos en `ml/experiments/` — ver [`../ml/README.md`](../ml/README.md).

1. **Sintético** — CSV en `data/synthetic/`.
2. **Mart** — `data/processed/paradigm_mart.db` (DDL + carga + vistas SQL).
3. **Calidad** — ejecuta checks en Python y escribe **`reports/quality_report.md`**.

### Cómo se ejecuta la calidad

```bash
python scripts/run_data_quality.py
```

**PYTHONPATH:** el script añade `python/src` al path; no hace falta `pip install -e .` para desarrollo local.

**Código de salida:** `0` si no hay checks con severidad **fail**; `1` si alguno falla. Los **warn** (p. ej. atendidas sin facturación en datos sintéticos) **no** cambian el código de salida.

### Qué valida

Resumen (detalle en código: `paradigm/quality/checks.py`):

| Tema | Comportamiento |
|------|----------------|
| Integridad | `PRAGMA integrity_check`, `PRAGMA foreign_key_check` |
| Unicidad | `appointment_id`, `billing_line_id` sin duplicados |
| Nulos | Columnas obligatorias en hechos |
| Fechas | `booking_date` ≤ `appointment_date` |
| Estados | Cancelada ↔ `cancellation_ts`; motivo solo si cancelada |
| Montos | `line_amount` ≥ 0; moneda `ARS` |
| Referencias | Líneas de facturación con `appointment_id` existente |
| `dim_date` | Toda `appointment_date` existe en calendario |
| Atención vs facturación | **WARN** si hay atendidas sin líneas (esperado en el sintético para demo de conciliación) |

### Artefacto

| Archivo | Descripción |
|---------|-------------|
| `reports/quality_report.md` | Tabla de resultados + leyenda; apto para portfolio o CI. |

### Límites de esta fase

- No valida CSV **antes** del load (la verdad operativa es el SQLite post-`build_sqlite_mart.py`).
- No sustituye tests unitarios exhaustivos ni reglas de negocio clínicas.
- Un **WARN** no bloquea el pipeline; revisar el detalle antes de publicar dashboards.

## Otros

- `notebooks/` — EDA opcional.

## Ver también

- [`sql/README.md`](../sql/README.md) — DDL, vistas, muestras SQL.
- [`docs/data_dictionary.md`](../docs/data_dictionary.md) — contrato de datos.
