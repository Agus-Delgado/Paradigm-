# Motor prescriptivo unificado (no-show)

**Fecha:** 2026-07-22
**Paquete:** `python/src/paradigm/prescriptive/`
**CLI:** `scripts/run_prescriptive_engine.py`
**JSON:** `ml/experiments/prescriptive_engine_report.json`
**Alcance:** Decide layer headless — **sin UI ni chat**.

---

## 1. Arquitectura

```text
predictions (risk ± uplift)
        │
        ▼
┌───────────────────────┐
│ normalize_decision_   │  risk, uplift, ENV=B·τ−C, incertidumbre
│ inputs                │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ select_operating_     │  none | uplift | risk  (regla de lab)
│ policy                │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ build_recommendations │  acción, scores, prioridad, explicación
│ + compare_policies    │  none/treat_all/random/risk/uplift/net_value
└───────────────────────┘
```

| Módulo | Rol |
|--------|-----|
| `config.py` | Costos, capacidad, calidad uplift, ATE asumido |
| `policy_selector.py` | Regla operativa automática / forced |
| `engine.py` | Normalización, ranking, salida estructurada, comparación |
| Reutiliza | `ml_v2.uplift_decision_policy.select_indices` (capacidad) |

**No modifica** modelos de riesgo/uplift ni `ml/prescriptive` (UI legacy).

---

## 2. Regla de política (actual)

1. **`forced_policy`** si se setea (tests / what-if).
2. **`none`** si `intervention_cost > B · uplift_ref`
   (`uplift_ref` = media de uplift estimado si hay; si no, `assumed_ate=0.055`).
3. **`uplift`** solo si hay uplift por cita **y** `uplift_quality ≥ 0.75`.
4. Default: **`risk`**.

Políticas soportadas en comparación: `none`, `treat_all`, `random`, `risk`, `uplift`, `net_value`.

Defaults económicos: \(B{=}10\), \(C{=}0.4\), capacidad \(\min(30,\lfloor 0.2 n\rfloor)\).

---

## 3. Salida por cita

| Campo | Descripción |
|-------|-------------|
| `recommended_action` | `intervene` \| `do_not_intervene` |
| `risk_score` | \(P(\text{no-show})\) |
| `uplift` | \(\hat\tau\) o ATE asumido |
| `expected_net_value` | \(B\cdot\hat\tau - C\) |
| `priority` | 1…k si interviene; 0 si no |
| `explanation` | Motivo breve + política |
| `policy_used` | Política aplicada |
| `uncertainty` | margen a 0.5, uplift disponible/fuente, calidad |

---

## 4. Ejecución moderate / strong

Fuente: predicciones RF de runs `no_show_v2_signal_{moderate,strong}_seed42` (sin uplift real → `uplift_quality=0` → política **risk**).

| Escenario | n | Política | Capacidad | Intervenidos | Motivo |
|-----------|---|----------|-----------|--------------|--------|
| moderate | 305 | **risk** | 30 | 30 | default risk (uplift unavailable); C < B·ATE |
| strong | 310 | **risk** | 30 | 30 | idem |

Ejemplo de fila (prioridad 1):

```json
{
  "appointment_id": "APT-01226",
  "recommended_action": "intervene",
  "risk_score": 0.652,
  "uplift": 0.055,
  "expected_net_value": 0.15,
  "priority": 1,
  "explanation": "Intervenir por política `risk`: alto riesgo (0.65); uplift asumido (ATE ref.). Motivo selección: default risk (uplift unavailable).",
  "policy_used": "risk",
  "uncertainty": {
    "risk_margin_to_0_5": 0.152,
    "uplift_available": false,
    "uplift_source": "assumed_ate",
    "uplift_quality": 0.0
  }
}
```

Con `--uplift-quality 0.8` y predicciones de `policy_intervention`, el motor pasa a **`uplift`**. Con `--intervention-cost 10`, cae a **`none`**.

---

## 5. Limitaciones

- Moderate/strong no tienen Two-Model: uplift es **ATE de referencia**, no individual.
- `uplift_quality` es un input externo (no se estima aquí).
- Sin UI/chat; `ml/prescriptive` legacy sigue aparte.

```bash
python scripts/run_prescriptive_engine.py --scenarios moderate strong
pytest tests/test_prescriptive_engine.py -v
```
