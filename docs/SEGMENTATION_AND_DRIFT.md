# Segmentación y monitoreo de drift

**Fecha:** 2026-07-22
**Código:** `python/src/paradigm/monitoring/`, `scripts/run_segmentation_drift.py`
**Datos:** `data/synthetic_v2/signal_moderate_seed42` (citas elegibles; features predecisionales)
**JSON:** `ml/experiments/segmentation_drift_report.json`
**Run:** `ml/experiments/runs/20260722_041109_segmentation_drift_signal_moderate_seed42/`
**Alcance:** clustering + drift por ventanas. **No** conecta segmentos a decisiones ni modifica modelos de riesgo/uplift/forecast.

---

## 1. Diseño compacto

| Pieza | Implementación |
|-------|----------------|
| Unidad | Cita (`appointment_id`) |
| Features | Solo predecisionales (`ml_v2.features`); sin truth / post-outcome / intervención |
| Modelo | KMeans (`n_init=10`) + `StandardScaler` + One-Hot |
| K | Comparación silhouette en \(K\in\{2,3,4,5\}\); se elige máx. silhouette |
| Estabilidad | ARI medio entre seeds `{0..4}` + ARI bootstrap |
| Perfiles | tamaño, lead, hora, % repeat, canal/especialidad moda, prevalencia no-show (solo reporte) |
| Drift | PSI (numéricas), TV distance (categóricas), Δ prevalencia outcome |
| Ventanas | 3 cuantiles temporales de `appointment_date` (ref = ventana 0) |

---

## 2. Resultados (signal_moderate_seed42, n=1638)

### Comparación de K

| K | Silhouette |
|---|------------|
| **2** | **0.116** |
| 3 | 0.110 |
| 4 | 0.107 |
| 5 | 0.086 |

**K elegido: 2** (silhouette bajo ⇒ separación débil en el espacio predecisional, esperable en sintético homogéneo).

### Estabilidad

| Métrica | Valor |
|---------|-------|
| mean pairwise seed ARI | **1.00** |
| mean bootstrap ARI | **0.96** |
| `stable` (ARI≥0.7) | **sí** |

Los labels son muy estables a la inicialización pese al silhouette bajo.

### Segmentos encontrados

| Cluster | n | share | lead medio | % repeat | canal moda | especialidad moda | prevalencia no-show |
|---------|---|-------|------------|----------|------------|-------------------|---------------------|
| **0** | 876 | 53.5% | 11.4 | 79.5% | PHONE (2) | 2 | 13.5% |
| **1** | 762 | 46.5% | 12.1 | **100%** | PHONE (2) | 1 | 14.4% |

Lectura: el eje dominante es **historial / recurrencia** (cluster 1 = solo pacientes repeat; cluster 0 mezcla first + repeat) y especialidad moda distinta. Prevalencias de no-show casi iguales.

### Ventanas temporales

| Ventana | Fechas | n | Prevalencia no-show |
|---------|--------|---|---------------------|
| 0 (ref) | 2024-01-02 → 2024-08-27 | 546 | 14.7% |
| 1 | 2024-08-29 → 2025-05-01 | 548 | 13.0% |
| 2 | 2025-05-02 → 2025-12-31 | 544 | 14.2% |

Δ prevalencia vs ref: −1.7 pp (v1), −0.5 pp (v2) → **sin alerta** (umbral 3 pp).

---

## 3. Principales señales de drift

Alertas recurrentes (PSI≥0.2 o TV≥0.15) vs ventana 0:

| Señal | Tipo | Por qué aparece |
|-------|------|-----------------|
| `provider_prior_*` / `patient_prior_*` | PSI muy alto | Contadores históricos **crecen con el tiempo** (drift estructural del feature engineering) |
| `appointment_month` | PSI alto | Estacionalidad de calendario entre ventanas |
| `coverage_id` / `booking_channel_id` / `provider_id` | TV moderada | Mezcla de categorías leve entre periodos |
| Prevalencia no-show | estable | Sin alerta |

También hay **cambio de composición de clusters** entre ventanas (`cluster_share_l1` alto): el mismo modelo global asigna proporciones distintas cuando los priors se inflan.

---

## 4. Limitaciones

- Silhouette bajo: segmentos interpretables pero no muy compactos.
- Drift de priors es en gran parte **artefacto temporal**, no necesariamente cambio de población.
- Un solo dataset/seed en el reporte operativo.
- No hay linkage a políticas, uplift ni forecasting.

---

## 5. Reproducir

```bash
python scripts/run_segmentation_drift.py --dataset-id signal_moderate_seed42
pytest tests/test_segmentation_drift.py -v
```
