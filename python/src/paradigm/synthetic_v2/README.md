# Synthetic data generator v2 (known ground truth)

Isolated from the legacy MVP generator (`scripts/generate_paradigm_v2_synthetic.py` → `data/synthetic/`).

## Quick start

From the repository root:

```bash
python scripts/generate_synthetic_v2.py --scenario signal_moderate --seed 42
python scripts/generate_synthetic_v2.py --scenario signal_weak --seed 42
python scripts/generate_synthetic_v2.py --scenario signal_strong --seed 42
```

## Probability model (summary)

\[
\eta = \beta_0 + \kappa\cdot f(X) + u_p + v_j + s(t),\quad
p_{\mathrm{true}}=\mathrm{clip}(\sigma(\eta)),\quad
Y\sim\mathrm{Bernoulli}(\mathrm{clip}(\sigma(\eta+\varepsilon)))
\]

`true_logit` / `true_no_show_probability` store the systematic propensity (no \(\varepsilon\)). Sampling noise \(\varepsilon\) controls difficulty.

**Intercept calibration:** deterministic bisection of \(\beta_0\) so the *expected* eligible no-show rate (covariates + latents + competing cancellation + \(E_\varepsilon[p]\)) matches `target_no_show_rate` (default `0.13` for all signal scenarios). Failure to converge aborts generation.

## Package layout

| Module | Role |
|--------|------|
| `contracts.py` | Typed config / truth / validation / result |
| `defaults.py` | `signal_moderate` defaults + scenario factory |
| `calibrate.py` | Bisection of \(\beta_0\) |
| `probability.py` | Logit components |
| `generate.py` | In-memory generation |
| `persist.py` | CSV + JSON writers |
| `validate.py` | Checks + multiseed helper |
| `runner.py` | End-to-end orchestration |

Design: [`docs/SYNTHETIC_DATA_V2_DESIGN.md`](../../../../docs/SYNTHETIC_DATA_V2_DESIGN.md).
Validation report: [`docs/SYNTHETIC_V2_VALIDATION_REPORT.md`](../../../../docs/SYNTHETIC_V2_VALIDATION_REPORT.md).
