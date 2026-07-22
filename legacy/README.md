# Paradigm v1 (LEGACY)

Materiales de la **versión anterior**. Se conservan por compatibilidad y exploración
opcional. **No** son el camino portfolio (mart dimensional + Live Demo + lab v2).

Estado: **aislado** bajo `legacy/`. El Live Demo v2 aún importa lógica de
`legacy/app/core` vía [`app/conversational/legacy_bridge.py`](../app/conversational/legacy_bridge.py)
(profiling / findings / ingestion). No borrar este árbol mientras exista ese puente.

Mapa: [`docs/FINAL_ARCHITECTURE.md`](../docs/FINAL_ARCHITECTURE.md).

## Contents

| Path | Description |
|------|-------------|
| [`app/`](app/) | Streamlit CSV/XLSX explorer (flat tables). |
| [`data/sample/medical_clinic/`](data/sample/medical_clinic/) | Sample CSVs for the legacy demo. |
| [`scripts/`](scripts/) | `generate_medical_clinic_data.py`, `verify_dynamic_questions.py` (ad-hoc; fuera de Make/CI). |

## Running the legacy app (optional)

From the **repository root**:

```bash
pip install -r requirements-app.txt
streamlit run legacy/app/main.py
```

Default demo CSV: `legacy/data/sample/medical_clinic/medical_clinic_flat.csv`.

Regenerate samples:

```bash
python legacy/scripts/generate_medical_clinic_data.py
```

## Note on language

Legacy UI strings may remain in Spanish; current project docs outside `legacy/`
prefer English or bilingual portfolio README.
