# Política de decisión: uplift × costos

**Fecha:** 2026-07-22
**Código:** `paradigm.ml_v2.uplift_decision_policy`, `scripts/analyze_uplift_v2_policy.py`
**Entrada:** predicciones hold-out de runs uplift Two-Model (`*uplift_v2_policy_intervention_seed{41,42,43}`)
**JSON:** `ml/experiments/uplift_v2_decision_policy.json`
**Alcance:** no modifica modelos ni hiperparámetros; no reentrena uplift.

---

## 1. Valor por cita

Para cada cita del hold-out, con el modelo uplift seleccionado del run:

| Cantidad | Fórmula |
|----------|---------|
| Riesgo | \(\hat p_0 = \hat P(Y{=}1\mid X,T{=}0)\) |
| Uplift | \(\hat\tau = \hat p_0 - \hat p_1\) |
| Beneficio esperado | \(B\cdot\hat\tau\) |
| Costo de intervención | \(C\) (constante configurable) |
| Valor neto esperado (ENV) | \(B\cdot\hat\tau - C\) |

**Defaults económicos**

| Parámetro | Valor | Nota |
|-----------|-------|------|
| \(B\) (`benefit_per_avoided`) | 10 | valor por unidad de reducción de \(P(\text{no-show})\) |
| \(C\) (`intervention_cost`) | 0.4 | break-even en \(\hat\tau = C/B = 0.04\) (cerca del ATE\(_p\approx 0.055\)) |
| Capacidad | \(\min(30,\lfloor 0.2\cdot n\rfloor)\) | en estos hold-outs ⇒ **30** |
| `min_net_value` | 0 | política `net_value` solo trata si ENV ≥ 0 |

Con \(C\) constante, ordenar por ENV es **monótono** con uplift; `net_value` solo difiere de `uplift` al filtrar ENV &lt; 0.

**Evaluación (truth del generador):**
\(\text{true\_net} = B\cdot\sum_{i\in S}\text{true\_benefit}_i - C\cdot|S|\),
con \(\text{true\_benefit}=p_0-p_1\).

---

## 2. Políticas comparadas

| Política | Regla | Capacidad |
|----------|-------|-----------|
| `none` | no intervenir | — |
| `treat_all` | tratar a todos | **sin tope** (referencia de rentabilidad media) |
| `random` | muestra aleatoria | sí |
| `risk` | top por \(\hat p_0\) | sí |
| `uplift` | top por \(\hat\tau\) | sí |
| `net_value` | top por ENV entre ENV≥0 | sí |

El **ganador operativo** se elige solo entre políticas con capacidad.

---

## 3. Resultados (seeds 41–43)

Capacidad resuelta: **30** en las tres seeds. Modelo por seed: LR / RF / LR (el del run uplift).

### true_net por política

| Seed | none | treat_all (sin tope) | random@30 | **risk@30** | uplift@30 | net_value@30 |
|------|------|----------------------|-----------|-------------|-----------|--------------|
| 41 | 0 | 32.47 | 1.72 | **16.47** | 12.04 | 12.04 |
| 42 | 0 | 26.82 | 3.06 | **18.48** | 9.47 | 9.47 |
| 43 | 0 | 36.60 | 1.38 | **10.77** | 5.92 | 5.92 |
| **Media** | 0 | **31.96** | 2.05 | **15.24** | 9.14 | 9.14 |

### Ganador operativo

| Seed | Política | Capacidad usada | true_net | vs treat_all (sin tope) | vs uplift@30 |
|------|----------|-----------------|----------|-------------------------|--------------|
| 41 | **risk** | **30 / 30** | 16.47 | −16.0 | **+4.4** |
| 42 | **risk** | **30 / 30** | 18.48 | −8.3 | **+9.0** |
| 43 | **risk** | **30 / 30** | 10.77 | −25.8 | **+4.9** |

**Política recomendada (con capacidad):** `risk` (mayor riesgo) — 3/3 seeds.
**Capacidad utilizada:** 30/30 (binding).
**vs treat_all:** peor en true_net porque treat_all no tiene tope y el ATE es rentable bajo \(B{=}10,C{=}0.4\); la brecha es de **capacidad**, no de ranking.
**vs uplift / net_value:** risk mejora **~+4.4 a +9.0** en true_net (media ~+6.1).
**vs random:** risk mejora ~+13 en media.

Con costo constante, `uplift` ≡ `net_value` en estas corridas (casi todos los top-30 tienen ENV&gt;0).

---

## 4. Sensibilidad a costos (seed 42, capacidad 30)

Ganador operativo bajo grilla \(B\in\{5,10,15,25\}\), \(C\in\{0.2,0.4,1.0,2.0\}\):

| | C=0.2 | C=0.4 | C=1.0 | C=2.0 |
|--|-------|-------|-------|-------|
| **B=5** | risk | risk | none* | none |
| **B=10** | risk | **risk** | risk / none† | none |
| **B=25** | risk | risk | risk | risk |

\*Con \(C\) alto relativo a \(B\cdot\text{ATE}\), no intervenir gana.
†En el borde, `none` puede empatar o superar a políticas activas si el costo por contacto supera el beneficio esperado medio del top-k.

Interpretación: si el recordatorio es barato respecto al valor de evitar no-show, conviene intervenir bajo capacidad priorizando **riesgo** (con el uplift Two-Model actual). Si \(C\) sube mucho, la óptima operativa es **none**.

---

## 5. Política recomendada

1. **Con capacidad limitada (default 30 / 20%):** priorizar por **mayor riesgo** (`risk`).
2. **Si la capacidad deja de ser binding** y \(B\cdot\text{ATE}&gt;C\): `treat_all` maximiza true_net (referencia).
3. **Uplift / ENV:** útiles como marco de decisión y para filtrar ENV&lt;0 cuando \(C\) es alto; con el Two-Model actual **no** superan a riesgo en true_net bajo capacidad 30.

No se cambia el training uplift; mejorar el estimator (más datos / X-Learner) es el camino para que `net_value` gane a `risk`.

---

## 6. Limitaciones

1. ENV usa uplift **predicho**; la métrica de selección usa **truth** — en producción habría que validar out-of-fold / IPW.
2. Costo homogéneo ⇒ `net_value` ≈ `uplift` salvo filtro ENV≥0.
3. El uplift Two-Model actual es ruidoso (ver `UPLIFT_V2_BASELINE_REPORT.md`); por eso el ranking por riesgo recupera más beneficio verdadero en el top-30.
4. `treat_all` sin tope no es operable bajo capacidad; sirve solo como techo económico.
5. No modela efectividad parcial del recordatorio distinta de la del generador.
6. Unidades abstractas (escalables a moneda).

---

## 7. Cómo reproducir

```bash
python scripts/analyze_uplift_v2_policy.py
python scripts/analyze_uplift_v2_policy.py --benefit 10 --intervention-cost 0.4 --capacity 30 --capacity-fraction 0.2
```
