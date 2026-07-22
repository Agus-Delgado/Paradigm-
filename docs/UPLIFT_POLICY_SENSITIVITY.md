# Sensibilidad de políticas: `risk` vs `uplift` vs `net_value`

**Fecha:** 2026-07-22
**Código:** `paradigm.ml_v2.uplift_policy_sensitivity`, `scripts/analyze_uplift_policy_sensitivity.py`
**Datos:** predicciones hold-out uplift seeds 41/42/43 (sin reentrenar; sin tocar generador)
**JSON:** `ml/experiments/uplift_v2_policy_sensitivity.json`
**Relacionado:** [`UPLIFT_DECISION_POLICY.md`](UPLIFT_DECISION_POLICY.md)

---

## 1. Diseño del análisis

### Políticas focus
`none`, `risk`, `uplift`, `net_value` (todas con capacidad, salvo que `none` no interviene).

### Grilla (240 celdas × 3 seeds)

| Eje | Valores |
|-----|---------|
| Capacidad | 10, 30, 50, 100 |
| Beneficio \(B\) | 5, 10, 25 |
| Costo \(C\) | 0.2, 0.4, 1.0, 2.0 |
| Calidad uplift \(q\) | 0, 0.25, 0.5, 0.75, 1.0 |

### Calidad del modelo uplift (sin cambiar el modelo)
Interpolación hacia la verdad del generador:

\[
\hat\tau_q = (1-q)\,\hat\tau_{\text{Two-Model}} + q\,\text{true\_benefit}
\]

- \(q=0\): modelo actual
- \(q=1\): oráculo de uplift (ranking perfecto por beneficio verdadero)

El **riesgo** \(\hat p_0\) no se interpola (calidad del risk model fija).

### Oráculo y regret
Oráculo = top-\(K\) por true ENV \(= B\cdot\text{true\_benefit}-C\) (con filtro ENV≥0).

\[
\text{regret}(\pi)=\text{true\_net}(\text{oracle})-\text{true\_net}(\pi)
\]

Ganador por celda = mayoría entre seeds (estabilidad = acuerdo 3/3).

---

## 2. Resumen global

| Métrica | Valor |
|---------|-------|
| Celdas | 240 |
| Estabilidad (acuerdo 3/3) | **82.5%** |
| Majority wins: `risk` | **90** (37.5%) |
| Majority wins: `none` | **75** (31.3%) |
| Majority wins: `uplift` | **63** (26.3%) |
| Majority wins: `net_value` | **12** (5.0%) |

---

## 3. Tablas de sensibilidad

### 3.1 Capacidad ( \(B{=}10\), \(C{=}0.4\), \(q{=}0\) ) — modelo actual

| Capacidad | Ganador | Acuerdo seeds | Regret medio risk | Regret uplift/net |
|-----------|---------|---------------|-------------------|-------------------|
| 10 | **risk** | 100% | 6.4 | 8.7 |
| 30 | **risk** | 100% | 13.4 | 19.5 |
| 50 | **risk** | 100% | 16.7 | 27.6 |
| 100 | **risk** | 100% | 21.3 | 38.0 |

Con el Two-Model actual, **más capacidad no hace ganar a uplift**: el regret de uplift crece más rápido que el de risk.

### 3.2 Costos × beneficio (capacidad 30, \(q{=}0\))

| | C=0.2 | C=0.4 | C=1.0 | C=2.0 |
|--|-------|-------|-------|-------|
| **B=5** | risk | risk* | **none** | **none** |
| **B=10** | risk | **risk** | none* | **none** |
| **B=25** | risk | risk | risk | risk* |

\*acuerdo parcial (2/3 seeds) en el borde.

**Regla empírica:** si \(C \gtrsim B\cdot\text{ATE}\) (ATE≈0.055 ⇒ umbral ~\(0.55\,B/10\)), gana **`none`**. Si \(B\) es alto (25), **risk** sigue ganando aunque \(C\) suba a 2.

### 3.3 Calidad uplift (capacidad 30, \(B{=}10\), \(C{=}0.4\))

| \(q\) | Ganador | Regret risk | Regret uplift | Regret net_value |
|-------|---------|-------------|---------------|------------------|
| 0.00 | **risk** | 13.4 | 19.5 | 19.5 |
| 0.25 | **risk** | 13.4 | 18.3 | 18.3 |
| 0.50 | **risk** | 13.4 | 15.7 | 15.7 |
| 0.75 | **uplift** | 13.4 | 10.7 | 10.7 |
| 1.00 | **uplift** | 13.4 | **0.0** | **0.0** |

Frontera clave: entre **\(q=0.5\) y \(q=0.75\)** el ganador pasa de `risk` → `uplift` (estable en 3 seeds).

### 3.4 Cuándo `net_value` ≠ `uplift`

Con \(C\) constante, ENV es monótono en uplift ⇒ misma ordenación si todos los top-K tienen ENV≥0.
`net_value` gana sobre `uplift` solo cuando el costo es **alto** y la calidad es **alta** (\(q{=}1\)): el filtro ENV≥0 evita tratar unidades con true ENV negativo (p.ej. cap=30, \(B{=}10\), \(C{=}2\), \(q{=}1\)).

---

## 4. Fronteras (cambios de ganador)

Patrones recurrentes en la grilla completa:

| Eje | Transición típica | Condición |
|-----|-------------------|-----------|
| **Calidad** | `risk` → `uplift` | \(q: 0.5 \to 0.75\), \(C\) bajo/medio |
| **Calidad** | `none` → `uplift`/`net_value` | \(q\to 1\) con \(C\) alto |
| **Costo** | `risk` → `none` | \(C: 0.4 \to 1.0\) con \(q\le 0.5\), \(B\in\{5,10\}\) |
| **Costo** | `uplift` → `net_value` | \(C\) alto y \(q{=}1\) (filtro ENV) |
| **Costo** | `net_value` → `none` | \(C\) aún más alto / \(B\) bajo |
| **Capacidad** | pocas fronteras de ganador | con \(q{=}0\) risk domina en todo \(K\); cambia más el *nivel* de regret que el ganador |

Corte defaults (\(K{=}30\), \(B{=}10\), \(C{=}0.4\), \(q{=}0\)):

1. Subir \(C\) a 1.0 → **`none`**
2. Subir \(q\) a ≥0.75 → **`uplift`**

---

## 5. Regret frente al oráculo

En defaults (\(K{=}30\), \(B{=}10\), \(C{=}0.4\), \(q{=}0\)):

| Política | true_net medio | Regret medio |
|----------|----------------|--------------|
| oracle | ~28.6 | 0 |
| **risk** | ~15.2 | **13.4** |
| uplift / net_value | ~9.1 | **19.5** |
| none | 0 | 28.6 |

Con \(q{=}1\), uplift/net_value alcanzan regret **0** (coinciden con el oráculo bajo ENV≥0). Risk mantiene regret ~13.4 (no usa truth de efecto).

---

## 6. Estabilidad entre seeds

- **82.5%** de celdas con el mismo ganador en 41/42/43.
- Inestabilidad concentrada en **bordes económicos** (\(C\approx B\cdot\text{ATE}\), p.ej. \(B{=}10,C{=}1\) o \(B{=}5,C{=}0.4\)).
- La frontera de calidad \(0.5\to 0.75\) es **estable** (100% acuerdo en el corte default).

---

## 7. Cuándo conviene cada política

| Política | Conviene cuando… |
|----------|------------------|
| **`risk`** | Uplift débil (\(q\lesssim 0.5\)), intervención rentable en media (\(C < B\cdot\text{ATE}\)), capacidad limitada. **Caso actual del Two-Model.** |
| **`uplift`** | Ranking de efecto fiable (\(q\gtrsim 0.75\)), \(C\) no extremo. Objetivo: minimizar regret causal. |
| **`net_value`** | Mismo que uplift **más** \(C\) alto relativo a \(B\): filtrar ENV&lt;0 evita sobre-tratar. Con \(C\) bajo ≈ uplift. |
| **`none`** | \(C\) alto y/o \(B\) bajo; o uplift malo que haría true_net negativo en el top-K. |

---

## 8. Recomendación operativa

1. **Hoy (modelo Two-Model, \(q\approx 0\)):** usar **`risk`** bajo capacidad, con \(B{=}10\), \(C{=}0.4\) (o cualquier régimen donde \(C \lesssim 0.5\cdot B/10\)).
2. **No usar uplift/net_value aún** para priorizar: regret ~45% mayor que risk en defaults.
3. **Revisar a uplift/net_value** solo si un estimator nuevo alcanza correlación/ranking cercano a \(q\gtrsim 0.75\) (validar con hold-out / off-policy).
4. **Si el costo real sube** cerca de \(C\ge 1\) con \(B{=}10\): preferir **`none`** o bajar capacidad drásticamente; con uplift oráculo, **`net_value`**.
5. Ampliar capacidad ayuda el true_net de risk, pero **no** cambia el ranking de políticas mientras \(q\) sea bajo.

---

## 9. Limitaciones

- \(q\) es un *proxy* de calidad (blend con truth), no un métrica de deployment.
- Risk no se degrada/mejora en la grilla (solo uplift).
- Unidades abstractas; recalibrar \(B,C\) a moneda real antes de operar.
- Oráculo usa potencial outcomes del generador (no disponible en producción).

## 10. Reproducir

```bash
python scripts/analyze_uplift_policy_sensitivity.py
pytest tests/test_uplift_policy_sensitivity.py -v
```
