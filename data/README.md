# Data — Paradigm v2

| Folder | Contents |
|--------|----------|
| `synthetic/` | **MVP** dimensional dataset (regenerable CSVs). Main source through the SQL mart. |
| `raw/` | Reserved for future “as-received” ingestions. |
| `processed/` | Pipeline output and **SQLite** database `paradigm_mart.db` (built with `scripts/build_sqlite_mart.py`; not versioned in Git). |

**Historical demo (v1):** legacy clinic sample CSVs live under [`../legacy/data/sample/medical_clinic/`](../legacy/data/sample/medical_clinic/) for the optional Streamlit app; **v2** uses `synthetic/` as the analytic contract.

Regenerate synthetic v2:

```bash
python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py
python scripts/run_data_quality.py
```

The last step writes `reports/quality_report.md` (mart validation). See [`python/README.md`](../python/README.md).
