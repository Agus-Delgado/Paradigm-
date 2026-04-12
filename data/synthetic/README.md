# Dataset sintético Paradigm v2 (MVP)

**Uso:** modelado dimensional y mart SQLite (`scripts/build_sqlite_mart.py`); datos **ficticios**.

**Regeneración:**

```bash
python scripts/generate_paradigm_v2_synthetic.py
```

**Parámetros:** `SEED=42`, `N_APPOINTMENTS=520`, rango de fechas `2024-01-02`–`2025-02-28`.

Ver [`docs/data_dictionary.md`](../../docs/data_dictionary.md).
