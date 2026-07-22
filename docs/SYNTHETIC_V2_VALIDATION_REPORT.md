# Informe de validación — generador sintético v2 (calibración)

**Fecha:** 2026-07-21
**Versión generador:** `2.1.0`
**Alcance:** calibración de prevalencia entre `signal_weak` / `signal_moderate` / `signal_strong` sin conexión a mart ni ML.
**Referencias:** [`SYNTHETIC_DATA_V2_DESIGN.md`](SYNTHETIC_DATA_V2_DESIGN.md), `paradigm.synthetic_v2`.

---

## 1. Método de calibración

Se reemplazó el grid aproximado del intercepto por **bisección determinista** de \(\beta_0\):

1. Tras muestrear covariables y latentes (orden cronológico fijo), se construye un **diseño de calibración**.
2. Para cada cita se calcula el logit sistemático \(f(X)\) (mismos efectos que en generación; `signal_scale` intacto).
3. La tasa previa de no-show en el diseño usa hipótesis **estacionaria**: 0 en primera cita del paciente; `target_no_show_rate` en repeticiones (el label aún no existe al calibrar). Los conteos de citas previas sí son exactos.
4. Cancelación competidora entra como peso \(w_i = 1 - \pi_{\mathrm{cancel},i}\).
5. Objetivo:

\[
\frac{\sum_i w_i\,\mathbb{E}_\varepsilon[\mathrm{clip}(\sigma(\beta_0 + f(X_i)+\varepsilon))]}{\sum_i w_i}
= \texttt{target\_no\_show\_rate}
\]

   con \(\mathbb{E}_\varepsilon\) por **Gauss–Hermite** (15 nodos).
6. Bisección hasta `|expected − target| ≤ calibration_tolerance` o ancho de bracket ≤ `calibration_xtol`.
7. **Sin convergencia → `CalibrationError` y no se escribe dataset.**

### Parámetros por defecto

| Parámetro | Default |
|-----------|---------|
| `target_no_show_rate` | `0.13` (común a los tres escenarios) |
| `calibration_tolerance` | `1e-4` (tasa **esperada**) |
| `calibration_max_iterations` | `80` |
| `calibration_xtol` | `1e-6` |
| Tolerancia tasa **observada** | \(\max(0.015,\ 2\sqrt{p(1-p)/n})\) |

`signal_scale` y el resto de coeficientes **no** se optimizan para AUC.

---

## 2. Resultados seed 42 (n = 2000 citas)

| Escenario | \(\beta_0\) calibrado | Tasa esperada | Tasa observada | \|err\| obs | AUC(`true_p`) | Iter. | Convergencia |
|-----------|----------------------|---------------|----------------|-------------|---------------|-------|--------------|
| `signal_weak` | −2.5156 | 0.12997 | 0.1310 | 0.0010 | **0.604** | 8 | sí |
| `signal_moderate` | −3.2422 | 0.12999 | 0.1392 | 0.0092 | **0.712** | 9 | sí |
| `signal_strong` | −4.4712 | 0.13001 | 0.1419 | 0.0119 | **0.814** | 13 | sí |

- Prevalencias observadas **comparables** (rango ≈ 0.131–0.142; spread ≈ 0.011).
- AUC estrictamente ordenado: weak < moderate < strong.
- Misma estructura de CSV/JSON y mismo conjunto de variables pre/post/truth.
- Rutas: `data/synthetic_v2/signal_{weak,moderate,strong}_seed42/`.

Artefactos de calibración en `generator_truth.json` y `validation_metrics.json`: intercepto, tasa esperada, tasa observada, errores, iteraciones, `converged`.

---

## 3. Evaluación multiseed (10 seeds)

- Seeds: `1…10`.
- Tamaño por corrida: `n_appointments=800`, `n_patients=100` (en memoria; sin I/O a `data/`).
- Función: `paradigm.synthetic_v2.evaluate_multiseed`.

| Escenario | Media tasa | Std tasa | Media AUC | Std AUC |
|-----------|------------|----------|-----------|---------|
| `signal_weak` | 0.131 | 0.008 | 0.607 | 0.036 |
| `signal_moderate` | 0.133 | 0.015 | 0.706 | 0.026 |
| `signal_strong` | 0.144 | 0.021 | 0.788 | 0.033 |

**Orden AUC weak < moderate < strong:** **10 / 10 (100%)**.

Interpretación: la calibración mantiene prevalencias cerca del target; strong muestra algo más de dispersión/sesgo residual (ruido de muestreo + priors realizados ≠ hipótesis estacionaria), pero el orden de señal es estable.

---

## 4. Criterios de aceptación finales

Una generación se aprueba si:

1. El solver de \(\beta_0\) **converge**.
2. `|tasa_esperada − target| ≤ calibration_tolerance`.
3. `|tasa_observada − target| ≤` tolerancia muestral (§1).
4. Probabilidades en clip y ≠ {0,1}.
5. Sin leakage pre/post en manifiestos.
6. Coherencia truth ↔ config (seed, escenario, \(\beta_0\), versión).
7. Para el trío de señal (mismo seed): prevalencias con spread razonable y AUC ordenado (verificado en tests + multiseed).

Tests añadidos/extendidos en `tests/test_synthetic_v2.py` (rutas temporales).

---

## 5. Limitaciones restantes

1. **Priors de no-show en calibración** son estacionarios (no el historial realizado); tras muestrear \(Y\), el término \(\beta_R R_i\) puede desplazar levemente la tasa observada vs la esperada.
2. La tasa observada sigue siendo estocástica (Bernoulli + cancelaciones + \(\varepsilon\)); la tolerancia muestral lo reconoce a propósito.
3. Escenarios drift / policy / missingness / anomalies **no** están en este informe.
4. `true_p` es la propensión **sin** \(\varepsilon\); el muestreo usa \(p(\eta+\varepsilon)\).
5. Aún **no** conectado al mart ni al pipeline de entrenamiento; `data/synthetic/` v1 intacto.

---

## 6. Validaciones ejecutadas

- `pytest tests/test_synthetic_v2.py` y `pytest tests/` (suite completa).
- Regeneración real de los tres escenarios con seed 42.
- Multiseed 10 seeds.
- Hashes SHA-256 de `data/synthetic/` v1 sin cambios.
- `git diff --check` limpio al cierre de esta tarea.
