# Forecasting baseline report — demanda diaria de citas

**Fecha:** 2026-07-22
**Código:** `ml/forecasting/*`, `scripts/benchmark_forecast_baselines.py`
**Datos:** `data/processed/paradigm_mart.db` → `fact_appointment` (sin filtros de especialidad; **sin cambiar datos**)
**JSON:** `ml/experiments/forecast_baseline_benchmark.json`
**Alcance:** benchmark de baselines + métricas; **no** conectado a decisiones / prescriptive.

---

## 1. Auditoría del módulo previo

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| Modelos | naive, seasonal_naive, prophet*, exp_smoothing* | + **moving_average**; *siguen opcionales |
| Métricas | MAE, RMSE, sMAPE | + **WAPE**, **MASE**, error **por horizonte** |
| Backtest | expanding window | documentado como **rolling-origin**; columna `horizon` |
| Selección | implícita / UI default `exp_smoothing` | **explícita: minimizar MASE** |
| Registro | `ExperimentTracker` legacy (un modelo) | cada baseline en `ml/experiments/runs/` (`experiment_type=forecasting`) |
| Tests | ausentes | `tests/test_forecasting_baselines.py` |

\*Prophet / Holt-Winters requieren deps no declaradas. En este entorno **statsmodels no está instalado** → `exp_smoothing` se omite del benchmark (no se agregó la dependencia).

Serie: **2024-01-02 → 2025-02-28**, 424 días, media ≈ 1.23 citas/día, **42% de días con 0**.

---

## 2. Protocolo del benchmark

| Parámetro | Valor |
|-----------|--------|
| Protocolo | Rolling-origin expanding |
| Horizonte H | 14 días |
| Step | 7 días |
| Train inicial | `max(56, 0.6·n)` = 254 |
| Folds | 23 |
| Predicciones pooled | 322 |
| Estacionalidad | 7 (semanal) |
| **Métrica de selección** | **`mase`** (menor es mejor) |

Modelos evaluados: `naive_last`, `seasonal_naive`, `moving_average`.
Omitido: `exp_smoothing` (falta `statsmodels`).

---

## 3. Resultados (pooled rolling-origin)

| Modelo | MAE | RMSE | WAPE % | sMAPE % | **MASE** | Run |
|--------|-----|------|--------|---------|----------|-----|
| naive_last | 1.516 | 1.935 | 122.6 | 124.0 | 1.503 | `…_forecast_baseline_naive_last_all` |
| moving_average | 1.245 | 1.549 | 100.7 | 126.3 | 1.235 | `…_forecast_baseline_moving_average_all` |
| **seasonal_naive** | **1.149** | 1.752 | **93.0** | **79.3** | **1.140** | `…_forecast_baseline_seasonal_naive_all` |

**Ganador (min MASE): `seasonal_naive`.**

MASE > 1 ⇒ el modelo no bate del todo al seasonal-naive *in-sample* usado como escala (el propio seasonal naive out-of-sample aún tiene error residual por cambios de nivel / calendario).

### Error por horizonte (ganador)

| h | MAE | Comentario |
|---|-----|------------|
| 1 | **1.91** | peor paso (origen del fold) |
| 2 | 1.57 | |
| 3–4, 10–11 | ~0 | fines de semana bien repetidos (0→0) |
| 8, 14 | ~1.83 | segundo ciclo semanal |

---

## 4. Comparación vs forecasting “actual” previo

Run legacy commitado `20260707_184421_demand_forecast_seasonal_naive_all`:

| | Legacy seasonal_naive | Benchmark actual |
|--|----------------------|------------------|
| MAE | 1.09 | 1.15 |
| RMSE | 1.64 | 1.75 |
| sMAPE | 78.8% | 79.3% |
| WAPE / MASE / por horizonte | no | sí |
| Protocolo | H≈7–14, step 7, train ~70% | H=14 fijo, train 60%, métricas pooled |

Misma familia de modelo y errores del mismo orden: el default frágil `exp_smoothing`/Prophet **no** era necesario para el baseline operable. El ganador del benchmark **confirma** seasonal naive como referencia correcta frente a naive y MA.

---

## 5. Principal fuente de error

1. **Demanda diaria muy sparse** (~42% ceros; media ~1.2): WAPE/sMAPE se inflan aunque MAE absoluto sea ~1 cita/día.
2. **Desajuste de nivel / DOW en días hábiles** (peor DOW=3; MAE en días no-cero ≈ 1.52 vs ≈ 0.69 en ceros).
3. **Peor en h=1**: el arranque de cada origen rolling captura saltos locales que el lag semanal no anticipa.

Driver etiquetado: `zero_inflation_sparse_daily_demand`.

---

## 6. Limitaciones

- Sin `statsmodels` / `prophet` en requirements → no se evaluó Holt-Winters ni Prophet aquí.
- No se agregaron modelos complejos (ARIMA, ML, deep).
- Fill de días faltantes con 0 puede crear ceros artificiales.
- No hay jerarquía por especialidad en este benchmark (scope ALL).
- **No** cableado a decisiones ni a capacidad operativa.

---

## 7. Recomendación

Usar **`seasonal_naive` (season=7)** como baseline de demanda diaria hasta tener deps o modelos más ricos; seleccionar siempre por **MASE** en el mismo protocolo rolling-origin. No conectar aún a Decide.

```bash
python scripts/benchmark_forecast_baselines.py
pytest tests/test_forecasting_baselines.py -v
```
