# Paradigm — Publication audit

**Fecha:** 2026-07-22
**Objetivo:** checklist previo a publicación pública (GitHub + demo).
**Veredicto tentativo:** ver sección final tras validaciones locales.

---

## 1. Archivos publicables

| Incluir | Motivo |
|---------|--------|
| Código `app/`, `python/src/paradigm/`, `ml/` (fuente), `scripts/`, `sql/`, `tests/` | Núcleo del laboratorio |
| `data/synthetic/*.csv` | Dataset dimensional reproducible (sintético) |
| `docs/**` | Arquitectura, case study, reportes de lab |
| `assets/screenshots`, `assets/dashboards`, `assets/landing` | Evidencia visual |
| `bi/**/source_csv`, guías BI | Consumo sin binarios `.pbix`/`.twbx` |
| `reports/quality_report.md`, `evaluation_gold_report.json` | Evidencia Learn |
| `ml/experiments/metrics.json` | Snapshot portfolio intencional |
| `requirements*.txt`, `Makefile`, `Dockerfile*`, CI | Reproducibilidad |
| `legacy/` | Aislado; documentado; aún requerido por `legacy_bridge` |
| `.env.example` | Plantilla sin secretos |
| `LICENSE`, `README.md` | Licencia + narrativa |

| Excluir / no commitear | Motivo |
|------------------------|--------|
| `.env`, `.streamlit/secrets.toml` | Secretos |
| `data/processed/*.db`, `*.joblib`, `rag_index/`, `*.jsonl` | Regenerables / runtime |
| `data/synthetic_v2/` | Lab generado (gitignore) |
| `ml/experiments/runs/` | Artefactos de experimentación |
| `.venv/`, `__pycache__/`, caches | Local |

---

## 2. Secretos

| Check | Estado |
|-------|--------|
| `.env` en `.gitignore` | Sí |
| `.streamlit/secrets.toml` ignorado | Sí |
| `.env.example` solo placeholders | Sí (`GROQ_API_KEY=`, etc. vacíos) |
| Hardcoded `sk-` / `ghp_` / keys en código | No encontrado (2026-07-22) |
| Keys solo vía `os.getenv` en `llm_config.py` | Sí |

**Acción manual:** confirmar que `.env` local **nunca** se agrega al staging; rotar cualquier key si alguna vez se filtró.

---

## 3. Artefactos pesados

| Ítem | ~Tamaño | Notas |
|------|--------:|-------|
| Repo tracked total | **~5,6 MB** | Aceptable para GitHub |
| `docs/images/paradigm-demo-loop.gif` | ~1,9 MB | Mayor archivo; opcional en README |
| Screenshots PNG | ~0,1–0,5 MB c/u | Portfolio evidence |
| `legacy/.../medical_clinic_flat.csv` | ~0,4 MB | Legacy sample |

No hay modelos `.joblib` ni FAISS trackeados tras la limpieza previa.
**Riesgo residual:** no re-agregar `ml/experiments/runs/` ni `rag_index/`.

---

## 4. Dependencias

| Archivo | Contenido | Público |
|---------|-----------|---------|
| `requirements.txt` | pandas, numpy, sklearn, shap, matplotlib, nbformat, openpyxl, joblib | Sí (CI) |
| `requirements-dev.txt` | + pytest | Sí |
| `requirements-llm.txt` | langchain*, faiss-cpu, sentence-transformers, dotenv | Opcional |
| `requirements-app.txt` | streamlit, plotly + core + llm | Demo |

Sin pin estricto (rangos `>=`): reproducible pero no bit-identical. Aceptable para portfolio; lockfile queda como mejora futura.

---

## 5. Tests

| Comando | Expectativa |
|---------|-------------|
| `pytest tests/ -v` | Suite completa (Observe…Learn) |
| Mapa | [`tests/README.md`](../tests/README.md) |

CI ejecuta la misma suite en push a `main`.

---

## 6. CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

1. Python 3.11 + `requirements.txt` + `requirements-dev.txt` (**sin** Streamlit)
2. Smoke imports core (incl. `paradigm.prescriptive`, `decision_layer`, `ml_v2`)
3. `pytest tests/ -v`
4. `build_sqlite_mart.py` → `run_data_quality.py` → `validate_executive_kpis.py`

**No cubre:** train ML, lab v2, uplift, Streamlit UI, eval LLM cloud.

---

## 7. Riesgos

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| `legacy_bridge` en camino crítico | Media | Documentado; no borrar `legacy/` |
| AUC débil mal interpretado | Alta (reputación) | Narrativa README + case study |
| Re-commit de runs/joblib | Media | `.gitignore` ampliado |
| Demo sin mart.db | Baja | README: `build_sqlite_mart` antes de Streamlit |
| Naming “v2” app vs lab | Baja | `FINAL_ARCHITECTURE.md` |
| Vercel no es el host nativo | Media | Streamlit Cloud / Docker / local; ver checklist |

---

## 8. Checklist GitHub

- [ ] README apunta a case study + publication audit + arquitectura final
- [ ] Licencia MIT visible
- [ ] Topics: `decision-intelligence`, `analytics-engineering`, `streamlit`, `prescriptive-analytics`, `synthetic-data`
- [ ] Descripción corta: *Decision Intelligence Laboratory — evidence to operational decisions (synthetic outpatient ops)*
- [ ] Secrets: Settings → Actions secrets solo si se usan (hoy CI no necesita API keys)
- [ ] Branch protection opcional en `main`
- [ ] Release / tag `v2.2` opcional tras merge
- [ ] Confirmar `git status` limpio de `.env` y `runs/`
- [ ] GIF/demo loop: mantener o mover a release assets si pesa en clone

---

## 9. Checklist Vercel / hosting demo

Paradigm es **Streamlit**, no una app Next/React estática.

| Opción | Notas |
|--------|-------|
| **Streamlit Community Cloud** | Encaje natural; conectar repo; `streamlit_app.py`; secrets de LLM opcionales |
| **Docker** (`docker compose`) | Ya soportado; bueno para demo controlada |
| **Vercel** | **No recomendado** como host primario (no es runtime Streamlit). Usar Vercel solo si hay un **landing estático** separado que enlace a la demo Streamlit |
| **Hugging Face Spaces** | Alternativa Streamlit |

Checklist si se publica demo online:

- [ ] Mart preconstruido o script de init en el host
- [ ] `PARADIGM_LLM_PROVIDER=disabled` o secrets de proveedor
- [ ] Banner de datos sintéticos visible
- [ ] Rate limits / sin PII (solo sintético)
- [ ] README “Demo” con URL pública

---

## 10. Veredicto

| Criterio | Resultado (2026-07-22) |
|----------|------------------------|
| Tests | **125 passed** (`pytest tests/ -v`) |
| App | Streamlit health **200** (`streamlit run` headless) |
| Pipelines | v1 `train_no_show` + v2 `train_no_show_v2` OK |
| Secretos | Sin tokens hardcodeados; `.env` gitignored |
| Tamaño tracked | ~**5,6 MB** (sin joblib/FAISS) |
| `git diff --check` | OK |

### Estado: **APTO para publicación** (con pasos manuales de GitHub/hosting)

Pasos manuales restantes: ver checklist §8–9 (topics, descripción, host Streamlit Cloud o Docker; **no** Vercel como runtime Streamlit).
