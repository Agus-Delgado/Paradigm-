# Umbral de decisión — no-show v2 (moderate / strong)

**Fecha:** 2026-07-21
**Entrada:** predicciones hold-out de runs `*no_show_v2_signal_{moderate,strong}_seed42`
**Código:** `paradigm.ml_v2.threshold_policy`, `scripts/analyze_no_show_v2_thresholds.py`
**JSON:** `ml/experiments/no_show_v2_threshold_analysis.json`
**Alcance:** no modifica modelos ni features.

---

## 1. Supuestos

| Parámetro | Default | Significado |
|-----------|---------|-------------|
| `cost_fp` | 1 | Costo de contactar a quien **no** iba a ser no-show |
| `cost_fn` | 5 | Costo de **no** contactar a un no-show real |
| `benefit_per_avoided` | 10 | Beneficio esperado si se interviene un TP (no-show evitado) |
| `max_interventions` | 30 | Capacidad máxima de contactos en el hold-out |

**Política:** ordenar por score descendente; intervenir solo si `score ≥ umbral`, hasta agotar capacidad.

**Valor neto:**

\[
\text{Net} = B\cdot TP - C_{FP}\cdot FP - C_{FN}\cdot FN
\]

**Baseline “no hacer nada”:** \(Net_0 = -C_{FN}\cdot N_{+}\). Se reporta también `net_vs_noop = Net - Net_0`.

Unidades: abstractas (escalables a ARS). Efectividad de la intervención = 1 (todo TP se “evita”).

Umbrales evaluados: 0.05 … 0.95 (paso 0.05). Selección: maximizar `net_value`; empates → mayor F1 → menor `n_intervened` → mayor umbral.

---

## 2. Comparación por modelo (defaults)

### signal_moderate (n=305, prevalencia ≈ 13.8%, \(N_{+}=42\), \(Net_0=-210\))

| Modelo | Umbral | Capacidad usada | Binding | P | R | F1 | TP/FP/FN | Beneficio | Costo | Net | vs noop |
|--------|--------|-----------------|---------|---|---|----|----------|-----------|-------|-----|---------|
| **Logistic** | **0.65** | **25 / 30** | No | 0.320 | 0.190 | 0.239 | 8/17/34 | 80 | 187 | **−107** | **+103** |
| Random Forest | 0.50 | 30 / 30 | Sí | 0.233 | 0.167 | 0.194 | 7/23/35 | 70 | 198 | −128 | +82 |

Mejor por net (defaults): **Logistic**.

### signal_strong (n=310, prevalencia ≈ 10.0%, \(N_{+}=31\), \(Net_0=-155\))

| Modelo | Umbral | Capacidad usada | Binding | P | R | F1 | TP/FP/FN | Beneficio | Costo | Net | vs noop |
|--------|--------|-----------------|---------|---|---|----|----------|-----------|-------|-----|---------|
| Logistic | 0.60 | 30 / 30 | Sí | 0.267 | 0.258 | 0.262 | 8/22/23 | 80 | 137 | −57 | +98 |
| **Random Forest** | **0.55** | **30 / 30** | Sí | 0.300 | 0.290 | 0.295 | 9/21/22 | 90 | 131 | **−41** | **+114** |

Mejor por net (defaults): **Random Forest**.

Los nets absolutos son negativos porque \(C_{FN}\) sigue pagándose por los FN restantes bajo capacidad limitada; aun así la política mejora claramente frente a no intervenir.

---

## 3. Umbral recomendado por escenario

Bajo los defaults (`C_FP=1`, `C_FN=5`, `B=10`, capacidad=30):

| Escenario | Modelo recomendado | Umbral | Capacidad usada | Net esperado | Mejora vs noop |
|-----------|--------------------|--------|-----------------|--------------|----------------|
| moderate | Logistic | **0.65** | 25 | −107 | +103 |
| strong | Random Forest | **0.55** | 30 | −41 | +114 |

Si se fija el selected_model del pipeline (**RF**, paridad v1):

| Escenario | Umbral RF | Capacidad usada | Net | vs noop |
|-----------|-----------|-----------------|-----|---------|
| moderate | 0.50 | 30 | −128 | +82 |
| strong | 0.55 | 30 | −41 | +114 |

---

## 4. Sensibilidad a costos (RF)

Grilla: `cost_fn ∈ {2,5,10,20}`, `benefit ∈ {5,10,15,25}`, `cost_fp=1`, capacidad=30.

Patrones observados:

- Subir **benefit** mejora el net y suele **bajar o mantener** el umbral (más intervenciones valen la pena).
- Subir **cost_fn** empeora el net absoluto (FN residuales dominan) pero **aumenta** el valor de capturar TP; el umbral óptimo tiende a permitir llenar capacidad si el ranking es decente.
- En **strong**, con `benefit=15` y `cost_fn=5`, el net RF pasa a **+4** (umbrales ~0.55, n=30).
- En **moderate**, RF con defaults queda por detrás de logistic; hace falta mayor benefit o menor costo de FP para que RF lidere el net.

Detalle: `models.*.sensitivity` en el JSON.

---

## 5. Limitaciones

1. Hold-out sintético (~300 filas); umbrales no transferibles a producción clínica.
2. Efectividad de intervención = 1; en la práctica el beneficio por TP es menor.
3. Costos son supuestos de laboratorio, no tarifas reales.
4. Capacidad fija en el hold-out; no modela cola diaria ni horarios de call-center.
5. Scores con `class_weight=balanced` no están calibrados a prevalencia; el umbral óptimo no es 0.5 por magia probabilística.
6. No se cambió el `selected_model` del entrenamiento; este doc es capa **Decide**, no reentrena.

---

## 6. Reproducir

```bash
python scripts/analyze_no_show_v2_thresholds.py \
  --cost-fp 1 --cost-fn 5 --benefit 10 --capacity 30

pytest tests/test_no_show_v2_threshold_policy.py -v
```
