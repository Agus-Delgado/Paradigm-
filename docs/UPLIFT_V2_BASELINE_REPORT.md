# Baseline uplift v2 — Two-Model sobre `policy_intervention`

**Fecha:** 2026-07-22
**Pipeline:** `paradigm.ml_v2.uplift_train` + `scripts/train_uplift_v2.py`
**Datos:** `data/synthetic_v2/policy_intervention_seed{41,42,43}/`
**Split:** temporal por `appointment_date` (test_ratio=0.2)
**Enfoque:** Two-Model (un clasificador en control \(T=0\), otro en tratados \(T=1\))
**Fuera de alcance:** conexión a política de costos / umbrales; otros metalearners (T-Learner ya; no X/R/Causal Forest).

## Definición

| Concepto | Definición |
|----------|------------|
| Tratamiento \(T\) | `extra_reminder` (recordatorio adicional) |
| Outcome \(Y\) | `target_no_show` (1 = NO_SHOW) |
| Score de uplift | \(\hat\tau(X)=\hat p(Y{=}1\mid X,T{=}0)-\hat p(Y{=}1\mid X,T{=}1)\) |
| Beneficio verdadero (eval) | \(p_0-p_1=-\texttt{true\_ite\_probability}\) |
| Features | Solo predecisionales (`ml_v2.features`) |
| Excluido | Truth, potential outcomes, \(T\), `intervention_cost`, post-outcome |

Selección de modelo por run: **mayor `qini_coefficient` en hold-out**.

## Runs

| Seed / dataset | run_id | Modelo elegido |
|----------------|--------|----------------|
| 41 / `policy_intervention_seed41` | `20260722_033058_uplift_v2_policy_intervention_seed41` | **logistic_regression** |
| 42 / `policy_intervention_seed42` | `20260722_033059_uplift_v2_policy_intervention_seed42` | **random_forest** |
| 43 / `policy_intervention_seed43` | `20260722_033100_uplift_v2_policy_intervention_seed43` | **logistic_regression** |

Artefactos: `ml/experiments/runs/<run_id>/` (`metrics.json`, `models/uplift_*_{control,treated}.joblib`, `predictions/test_uplift_predictions.csv`, `report.md`).

## Métricas hold-out (modelo seleccionado)

Beneficio en escala de probabilidad (reducción esperada de no-show).
Policy value @20% = media de beneficio verdadero en el top 20% del score.
Baselines: **random** (misma fracción, \(E[\text{benefit}]\)) y **treat_all** (\(E[\text{benefit}]\) sobre todo el test).

| Seed | Modelo | Qini | Spearman(score, true_benefit) | PV @20% | Δ vs random @20% | Treat-all (ATE_p≈) |
|------|--------|------|-------------------------------|---------|------------------|--------------------|
| 41 | Logistic | **0.114** | 0.143 | 0.064 | **+0.013** | 0.051 |
| 42 | RF | **0.146** | 0.146 | 0.063 | **+0.014** | 0.049 |
| 43 | Logistic | **0.038** | 0.059 | 0.057 | **+0.006** | 0.051 |

### Comparación LR vs RF (todas las seeds)

| Seed | LR Qini | RF Qini | LR PV@20% | RF PV@20% |
|------|---------|---------|-----------|-----------|
| 41 | 0.115 | −0.249 | 0.064 | 0.045 |
| 42 | −0.155 | 0.146 | 0.042 | 0.063 |
| 43 | 0.038 | −0.085 | 0.057 | 0.048 |

**Lectura:** el ranking supera a azar cuando el modelo seleccionado gana (Qini > 0; PV@20% > treat-all/random). RF es inestable entre seeds (muy negativo en 41/43); Logistic gana 2/3 seeds. No hay un único ganador absoluto — la regla operativa es **max Qini por run**.

### Uplift por deciles (ejemplo seed 42, RF seleccionado)

| Decil | n | mean predicted uplift | mean true benefit |
|-------|---|----------------------|-------------------|
| 1 (top) | ~31 | alto | **0.072** |
| 10 (bottom) | ~31 | bajo | 0.047 |

Monotonía imperfecta pero el top decil concentra más beneficio verdadero que el fondo.

## Segmentos prioritarios (recuperación)

Efecto verdadero del generador (doc intervención): mayor en **lead largo**, **WEB**, hora tarde, primera visita.

**Top 20% del modelo seleccionado — lift de prevalencia vs base del test:**

| Seed | Modelo | Δ lead≥15 | Δ WEB | Δ hour≥15 | Δ first | recovers? |
|------|--------|-----------|-------|-----------|---------|-----------|
| 41 | LR | +0.02 | **+0.05** | −0.07 | −0.02 | sí (WEB/lead) |
| 42 | RF | **+0.15** | **+0.15** | +0.09 | −0.03 | **sí (fuerte)** |
| 43 | LR | −0.02 | −0.05 | −0.21 | 0.00 | no |

**Capacidad de recuperar segmentos de alto efecto:** parcial. En seed 42 (RF) el top-20% concentra claramente WEB y lead largo. En 41, Logistic recupera WEB/lead débilmente. En 43 el ranking es débil (Qini bajo) y **no** recupera esos segmentos.

## Hiperparámetros

Iguales al risk model v2 (por brazo):

- Logistic: `lbfgs`, `class_weight=balanced`, `max_iter=2000`
- RF: `n_estimators=120`, `max_depth=10`, `min_samples_leaf=5`, `class_weight=balanced`

## Limitaciones

1. **Two-Model** estima \(\mu_t(X)\) por separado; con ~1.6k elegibles y split temporal, cada brazo de train es pequeño → varianza alta (sobre todo RF).
2. Qini/policy value usan **truth** del generador; en producción no existiría `true_ite_probability` (habría que usar estimadores out-of-fold / IPW sobre outcome observado).
3. **No** hay política de costos: el score no se traduce a umbral óptimo costo–beneficio.
4. Asignación aleatoria del generador facilita identificación; un targeting futuro rompería el supuesto de overlap si no se modela propensidad.
5. Spearman ~0.06–0.15: ranking útil pero lejos del oráculo; no sustituye un metalearner más estable ni más datos.
6. `first_visit` casi ausente en top-20 en varias seeds (pocos first en test o el modelo prioriza otras interacciones).

## Conclusión operativa

- Usar el **modelo con mayor Qini del run** (hoy: Logistic en seeds 41/43, RF en 42).
- El pipeline **supera tratamiento aleatorio** en PV@20% cuando Qini>0 (~+0.6–1.4 pp de beneficio medio en el top-20% vs random).
- Recuperación de segmentos prioritarios: **sí en el mejor run (RF seed 42)**; inconsistente across seeds — no tratar la recuperación como garantizada sin más n o otro estimator.

Próximos pasos naturales (fuera de este baseline): metalearners (X-Learner), más appointments, y recién entonces cablear política de costos.
