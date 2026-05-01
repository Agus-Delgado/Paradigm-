# Datos — Paradigm v2

| Carpeta | Contenido |
|---------|-----------|
| `synthetic/` | Dataset **MVP** dimensional (CSVs regenerables). Fuente principal hasta el mart SQL. |
| `raw/` | Reservado para ingestas “como llegan” en fases futuras. |
| `processed/` | Salida del pipeline y **base SQLite** `paradigm_mart.db` (generada con `scripts/build_sqlite_mart.py`; no versionada en Git). |

**Historical demo (v1):** legacy clinic sample CSVs live under [`../legacy/data/sample/medical_clinic/`](../legacy/data/sample/medical_clinic/) for the optional Streamlit app; **v2** uses `synthetic/` as the analytical contract.

Regenerar sintético v2:

```bash
python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py
python scripts/run_data_quality.py
```

El último paso genera `reports/quality_report.md` (validación del mart). Ver [`python/README.md`](../python/README.md).
