# Análisis de error — no-show v2

**Fecha:** 2026-07-21
**Entrada:** runs `*no_show_v2_signal_{weak,moderate,strong}_seed42` + reentrenos multi-seed (mismas features/hiperparámetros).
**Código:** `paradigm.ml_v2.error_analysis`, `scripts/analyze_no_show_v2.py`
**Artefactos:** `ml/experiments/no_show_v2_error_analysis.json`, curvas en `ml/figures/no_show_v2_error/`
**Umbral de decisión binaria:** 0.5 (no optimizado).

No se modificaron features, modelos ni hiperparámetros del pipeline de entrenamiento.

---

## 1. Resumen ejecutivo

| Escenario | Mejor ranking (ROC-AUC) | Mejor calibración (\|slope−1\|+\|intercept\|) | ¿RF sigue siendo buena selección? |
|-----------|-------------------------|-----------------------------------------------|-----------------------------------|
| weak | **Logistic** (0.568 vs 0.506) | **Logistic** | No: RF ≈ azar; conviene baseline o no priorizar |
| moderate | **RF** (0.646 vs 0.622) | **RF** | **Sí** — gana ranking y calibración; menos FP |
| strong | **Logistic** (0.711 vs 0.698) | **RF** | Empate útil: RF más calibrado / menos FP; LR ligeramente mejor AUC |

**Modelo mejor calibrado en conjunto (moderate + strong):** Random Forest (slope más cerca de 1 y menor desviación conjunta; Brier ≤ logistic).
**En weak:** ambos mal calibrados; logistic menos peor.

---

## 2. Calibración (hold-out seed 42)

Regresión: \(\mathrm{logit}\,P(Y{=}1) \approx a + b\,\mathrm{logit}(\hat p)\). Ideal: \(b{=}1\), \(a{=}0\).

| Escenario | Modelo | Slope \(b\) | Intercept \(a\) | Brier | Desv. cal. |
|-----------|--------|-------------|-----------------|-------|------------|
| weak | Logistic | 0.585 | −1.757 | 0.167 | 2.17 |
| weak | RF | 0.083 | −2.001 | 0.147 | 2.92 |
| moderate | Logistic | 0.509 | −1.661 | 0.198 | 2.15 |
| moderate | RF | **1.137** | −1.328 | **0.174** | **1.47** |
| strong | Logistic | 0.673 | −1.696 | 0.142 | 2.02 |
| strong | RF | **0.823** | −1.618 | **0.137** | **1.80** |

Curvas (quantile bins): `ml/figures/no_show_v2_error/calibration_<scenario>_<model>.png`.

**Lectura:** `class_weight=balanced` empuja scores hacia arriba y deja interceptos muy negativos (sobre-alerta relativa a la prevalencia ~0.10–0.14). RF en moderate/strong recupera slope cercano a 1; en weak el slope ~0 indica scores casi no informativos.

### Deciles de riesgo (RF, extracto)

- **weak:** predicción media y tasa observada se solapan cerca del base rate; gaps pequeños en magnitud pero sin ranking útil.
- **moderate:** deciles altos concentran más positivos; gaps de calibración moderados en colas.
- **strong:** mejor separación predicha vs observada en deciles superiores (coherente con AUC ~0.70).

Detalle numérico en el JSON (`models.random_forest.risk_deciles`).

---

## 3. Falsos positivos / negativos (umbral 0.5)

| Escenario | Modelo | TP | FP | TN | FN |
|-----------|--------|----|----|----|----|
| weak | Logistic | 2 | 11 | 258 | 32 |
| weak | RF | 3 | 9 | 260 | 31 |
| moderate | Logistic | 18 | **68** | 195 | 24 |
| moderate | RF | 9 | **30** | 233 | 33 |
| strong | Logistic | 12 | 44 | 235 | 19 |
| strong | RF | 14 | **35** | 244 | **17** |

- **Logistic** tiende a **más FP** (sobre todo moderate: 68), típico de balanced + umbral 0.5.
- **RF** reduce FP; en strong también reduce FN respecto de logistic.
- En **weak**, casi todos los positivos son FN: el umbral 0.5 no sirve para captura operativa.

---

## 4. Errores por segmento (RF)

Segmentos con **FN rate alta** suelen tener n chico o pocos positivos; interpretar con cautela.

### Hallazgos críticos

1. **Lead corto (0–3 / 4–7):** FN rate alta en weak/moderate — el modelo no marca riesgo cuando el lead es bajo (coherente con generador donde lead alto ↑ riesgo; scores bajos ⇒ no cruzan 0.5).
2. **Canal PHONE / RECEPTION:** en moderate/strong, FN rate 1.0 en varios cortes — el score medio queda bajo el umbral aunque haya no-shows; **WEB** concentra más scores altos (efecto canal + interacción lead×WEB en la verdad).
3. **Horario 8–11:** FN elevado en weak/moderate (mañana = menor riesgo generado ⇒ scores bajos ⇒ FN si hay positivos residuales).
4. **Especialidad:** Cardiología / Ginecología aparecen con FN rate alta en weak/moderate (n medio; ruido + heterogeneidad).
5. **Recurrencia:** casi todo el hold-out es `repeat` (pocas primeras visitas en la cola temporal) — poca potencia para comparar first vs repeat.

Logistic en moderate falla por **FP masivos** en los mismos segmentos de alta score (tarde, WEB, lead largo): alerta de más, captura más recall a costa de precisión.

---

## 5. Logistic vs Random Forest

| Dimensión | Weak | Moderate | Strong |
|-----------|------|----------|--------|
| ROC-AUC | LR > RF | RF > LR | LR ≳ RF |
| PR-AUC | LR > RF | RF > LR | LR ≳ RF |
| Brier | RF ≤ LR | RF < LR | RF ≤ LR |
| Calibración | LR mejor | **RF mejor** | **RF mejor** |
| FP @0.5 | similares (bajos) | LR mucho peor | LR peor |
| FN @0.5 | ambos altos | similares | RF ligeramente mejor |

---

## 6. Estabilidad (5 seeds: 1–5)

Reentreno con las mismas hiperparámetros; split temporal fijo ⇒ **Logistic es bit-estable** (std AUC = 0). RF varía poco:

| Escenario | RF AUC mean ± std | RF Brier mean ± std |
|-----------|-------------------|---------------------|
| weak | 0.533 ± 0.007 | 0.148 ± 0.003 |
| moderate | 0.638 ± 0.016 | 0.174 ± 0.005 |
| strong | 0.695 ± 0.012 | 0.141 ± 0.003 |

Orden de dificultad weak < moderate < strong se mantiene en la media de RF.

---

## 7. ¿RF sigue siendo la mejor selección?

- **Como default de portfolio (paridad v1):** razonable **si el escenario de trabajo es moderate/strong**: mejor o igual calibración, menos FP, ranking competitivo.
- **No** como selección única en **weak**: ahí RF no aporta ranking; logistic tampoco es “bueno”, solo menos malo.
- En **strong**, si el KPI es solo ROC-AUC, logistic gana por poco; si el KPI es **calibración / Brier / FP**, RF es preferible. Para priorización con contacto costoso, RF encaja mejor.

Recomendación operativa sintética: **mantener RF como selected_model**, reportar siempre logistic como baseline, y **no usar umbral 0.5** sin recalibrar (isotonic/Platt o umbral por capacidad de contacto).

---

## 8. Limitaciones

1. Hold-out temporal (~300 filas) ⇒ métricas de segmento ruidosas; FN rate = 1.0 no implica fallo sistemático si hay 1–3 positivos.
2. Umbral 0.5 fijo con `class_weight=balanced` sesga la matriz de confusión.
3. Multi-seed no regenera datos; solo estabilidad del ajuste sklearn.
4. Calibración slope/intercept asume logit-lineal; no sustituye diagramas por deciles.
5. Análisis post-hoc: no cambia el claim predictivo del experimento ni implica causalidad.

---

## 9. Cómo reproducir

```bash
python scripts/analyze_no_show_v2.py --seeds 1,2,3,4,5
pytest tests/test_no_show_v2_error_analysis.py -v
```
