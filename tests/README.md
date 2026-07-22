# Tests — mapa por capa

Suite unificada bajo `tests/`. CI ejecuta `pytest tests/ -v` con `PYTHONPATH=python/src` y **sin** Streamlit.

| Capa | Tests |
|------|--------|
| **Observe** | `test_synthetic_v2.py`, `test_synthetic_v2_intervention.py` (lab); calidad/KPI vía scripts en CI |
| **Predict** | `test_no_show_pipeline.py`, `test_no_show_determinism.py`, `test_no_show_v2_pipeline.py`, `test_forecasting_baselines.py`, `test_uplift_v2_pipeline.py` |
| **Explain** | `test_notebook_parser.py`, `test_notebook_analyzer.py`, `test_llm_integration.py` (LLM opcional; no requiere provider en asserts principales), `test_no_show_v2_error_analysis.py` |
| **Decide** | `test_prescriptive_engine.py`, `test_conversational_decision_layer.py`, `test_uplift_decision_policy.py`, `test_uplift_policy_sensitivity.py`, `test_no_show_v2_threshold_policy.py` |
| **Learn** | `test_experiment_runs.py`, `test_segmentation_drift.py`, `test_evaluation.py` |

Legacy / UI: no hay tests del app Streamlit v1; el puente `legacy_bridge` se ejercita indirectamente vía análisis conversacional donde aplica.
