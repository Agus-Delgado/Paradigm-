# Paradigm v1 (legacy)

This folder contains the **previous v1** materials for Paradigm. They are kept for reference and optional local exploration; **they are not the main v2 portfolio path** (dimensional mart, SQL, BI exports, and ML live at the repository root).

## Contents

| Path | Description |
|------|-------------|
| [`app/`](app/) | Streamlit-based CSV/XLSX explorer and optional clinic-style demo (flat tables). |
| [`data/sample/medical_clinic/`](data/sample/medical_clinic/) | Sample CSV files used by the legacy demo and by [`scripts/generate_medical_clinic_data.py`](../scripts/generate_medical_clinic_data.py) output. |

## Running the legacy app (optional)

From the **repository root**:

```bash
pip install -r requirements-app.txt
streamlit run legacy/app/main.py
```

The default demo CSV path is `legacy/data/sample/medical_clinic/medical_clinic_flat.csv`.

## Note on language

Legacy UI strings and some comments may remain in Spanish; the **current** project documentation (root `README.md`, `docs/`, and folder READMEs outside `legacy/`) is **English**.
