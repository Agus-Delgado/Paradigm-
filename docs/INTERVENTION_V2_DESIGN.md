# Intervención sintética v2 (`policy_intervention`)

**Estado:** implementado (generador + validación + tests).
**Fecha:** 2026-07-21
**Alcance:** extender Synthetic v2 con un tratamiento sintético y potential outcomes.
**Fuera de alcance:** entrenar modelos uplift, conectar política de umbral, modificar `paradigm.ml` / mart / risk models v1.

Entradas: [`SYNTHETIC_DATA_V2_DESIGN.md`](SYNTHETIC_DATA_V2_DESIGN.md), `python/src/paradigm/synthetic_v2/intervention.py`.

---

## 1. Propósito

Generar un escenario reproducible donde existe un **tratamiento asignado al azar** (recordatorio adicional) con:

1. Efecto **heterogéneo** por segmentos observables.
2. **Outcomes potenciales** \(Y(0)\), \(Y(1)\) y propensiones \(p_0\), \(p_1\).
3. **ITE verdadero** solo en columnas de truth (leakage si se usan como features de riesgo).
4. **Costo** de intervención por fila tratada.

Sirve para validar pipelines de evaluación causal / uplift **después**; este doc y el código **no** entrenan esos modelos todavía.

---

## 2. Tratamiento

| Campo | Definición |
|-------|------------|
| Tratamiento \(T\) | `extra_reminder` ∈ {0,1} — recordatorio **adicional**, distinto de `reminder_sent` (base) |
| Asignación | Bernoulli(\(\pi\)) si `lead_time_days ≥ require_lead_at_least` (default 1); si no, \(T=0\) |
| \(\pi\) | `intervention.treatment_prob` (default **0.5**, override CLI `--treatment-prob`) |
| Costo | `intervention_cost = cost_per_intervention` si \(T=1\), else `0` (default costo **1.0**) |

La asignación es **configurable** y **independiente** del score de riesgo (no policy targeting).

---

## 3. Fórmula (potential outcomes)

Partimos del logit de control del generador v2 (propensión sistemática + intercept calibrado):

\[
\eta_0 = \beta_0 + \kappa\, f(X) + u + v + s(t)
\]

\[
p_0 = \mathrm{clip}\bigl(\sigma(\eta_0)\bigr)
\]

Bajo tratamiento, el logit se desplaza por un efecto heterogéneo \(\Delta(X)\):

\[
\eta_1 = \eta_0 + \Delta(X),\qquad
p_1 = \mathrm{clip}\bigl(\sigma(\eta_1)\bigr)
\]

\(\Delta(X) < 0\) reduce \(P(\text{no-show})\). Defaults:

\[
\begin{aligned}
\Delta(X) &= \delta_{\text{base}} \\
&\quad + \delta_{\text{lead long}}\cdot\mathbf{1}[\text{lead}\ge 14] \\
&\quad + \delta_{\text{channel}}(c) \\
&\quad + \delta_{\text{late}}\cdot\mathbf{1}[\text{hour}\ge 15] \\
&\quad + \delta_{\text{first/repeat}}
\end{aligned}
\]

con \(\delta_{\text{base}}=-0.35\), \(\delta_{\text{lead long}}=-0.25\), \(\delta_{\text{WEB}}=-0.20\), \(\delta_{\text{PHONE}}=-0.05\), \(\delta_{\text{RECEPTION}}=0\), \(\delta_{\text{late}}=-0.10\), \(\delta_{\text{first}}=-0.15\), \(\delta_{\text{repeat}}=-0.05\).

**Acoplamiento de ruido:** el mismo \(\varepsilon\sim\mathcal{N}(0,\sigma_\varepsilon^2)\) y el mismo \(U\sim\mathrm{Unif}(0,1)\) generan:

\[
Y(0)=\mathbf{1}[U < p_0^{\text{sample}}],\quad
Y(1)=\mathbf{1}[U < p_1^{\text{sample}}],\quad
Y^{\text{obs}}=Y(T)
\]

donde \(p^{\text{sample}}=\mathrm{clip}(\sigma(\eta+\varepsilon))\).

**Efectos individuales (solo truth):**

\[
\text{ITE}_p = p_1 - p_0,\qquad
\text{ITE} = Y(1)-Y(0)
\]

**ATE verdaderos (sobre elegibles ATTENDED/NO_SHOW):**

\[
\text{ATE}_p = \mathbb{E}[\text{ITE}_p],\qquad
\text{ATE}_Y = \mathbb{E}[\text{ITE}]
\]

`true_no_show_probability` / `true_logit` observados corresponden al brazo realizado (\(T\)).

---

## 4. Supuestos

1. **SUTVA:** sin interferencia entre citas; un solo tratamiento binario.
2. **Ignorabilidad:** \(T \perp (Y(0),Y(1)) \mid\) elegibilidad de lead (asignación aleatoria).
3. **Positividad:** \(\pi\in(0,1)\) en citas con lead suficiente.
4. **No confusión residual en truth:** el efecto causal verdadero es \(\Delta(X)\) por construcción.
5. **Separación de roles:** `extra_reminder` / `intervention_cost` / columnas `true_*` de intervención **no** entran al feature set de riesgo (`ml_v2`); los modelos de riesgo existentes no se modifican.
6. **Calibración \(\beta_0\):** sigue apuntando a la prevalencia de **control** (~13%). Con ~50% tratados, la tasa **observada** cae (~9–10%); la validación lo admite explícitamente.

---

## 5. Columnas

### Asignación (observables de política, no features de riesgo)

- `extra_reminder`
- `intervention_cost`

### Truth / potential outcomes (solo artefacto de verdad)

- `true_logit_t0`, `true_logit_t1`
- `true_p0`, `true_p1`
- `true_ite_probability`
- `true_y0`, `true_y1`
- `true_ite`

---

## 6. Escenario `policy_intervention`

- Misma base de señal que `signal_moderate` + `InterventionParams(enabled=True)`.
- CLI: `python scripts/generate_synthetic_v2.py --scenario policy_intervention --seed 42`
- Salida: `data/synthetic_v2/policy_intervention_seed<seed>/`

Validaciones automáticas (`validate_intervention_block`):

| Check | Criterio |
|-------|----------|
| Balance T/C | tasa cerca de \(\pi\); max \|SMD\| en lead/hour/repeat \< 0.35 |
| ATE | \(\text{ATE}_p < 0\) (recordatorio reduce no-show) |
| Segmentos | CATE reportados por lead / canal / hora / recurrencia |
| Reproducibilidad | mismo seed ⇒ mismos fingerprints |
| Leakage | overlap vacío entre features predecisionales y truth/asignación |

---

## 7. Resultados (n≈2000 citas, seeds 41–43)

| Seed | Treatment rate | max \|SMD\| | ATE\(_p\) | ATE\(_Y\) | Noshow obs |
|------|----------------|------------|-----------|-----------|------------|
| 41 | 0.504 | 0.073 | **−0.0544** | −0.0483 | 0.090 |
| 42 | 0.490 | 0.108 | **−0.0545** | −0.0537 | 0.096 |
| 43 | 0.484 | 0.052 | **−0.0548** | −0.0555 | 0.098 |

**ATE de probabilidad (media ≈ −0.0545):** el recordatorio adicional reduce ~5.5 pp la \(p\) de no-show en promedio.

### Segmentos con mayor efecto (CATE\(_p\), más negativo)

Consistente en las 3 seeds:

1. **Lead largo** (`31+`, luego `15-30`): ≈ −0.08 a −0.09
2. **Canal WEB**: ≈ −0.083
3. **Hora tarde** (`15-17`): ≈ −0.066
4. **Primera visita** vs repeat: ≈ −0.061 vs −0.053

Menor efecto: lead corto (`0-3`) y canal RECEPTION (~−0.03).

---

## 8. Qué no se hace todavía

- No se entrenan modelos **uplift** / CATE estimators.
- No se conecta la **política de umbral** (`threshold_policy`) al tratamiento.
- No se cambia el training path de riesgo v1 ni se usa `extra_reminder` como feature predictiva.

Próximo paso natural: estimar uplift sobre features predecisionales y comparar contra `true_ite` / CATE de truth.
