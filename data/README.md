# Datos — Paradigm v2

| Carpeta | Contenido |
|---------|-----------|
| `synthetic/` | Dataset **MVP** dimensional (CSVs regenerables). Fuente principal hasta el mart SQL. |
| `raw/` | Reservado para ingestas “como llegan” en fases futuras. |
| `processed/` | Salida del pipeline y **base SQLite** `paradigm_mart.db` (generada con `scripts/build_sqlite_mart.py`; no versionada en Git). |

**Demo histórica (v1):** los archivos en `sample/medical_clinic/` siguen disponibles para la app Streamlit legacy; **v2** usa `synthetic/` como contrato analítico alineado al plan.

Regenerar sintético v2:

```bash
python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py
python scripts/run_data_quality.py
```

El último paso genera `reports/quality_report.md` (validación del mart). Ver [`python/README.md`](../python/README.md).
