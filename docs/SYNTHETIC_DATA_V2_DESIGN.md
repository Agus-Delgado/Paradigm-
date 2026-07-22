# Diseño del generador sintético v2 (verdad conocida, dificultad controlable)

**Estado:** diseño únicamente — **sin implementación**.
**Fecha de diseño:** 2026-07-21
**Entradas:** [`SYNTHETIC_DATA_AUDIT.md`](SYNTHETIC_DATA_AUDIT.md), [`EXPERIMENT_STANDARD.md`](EXPERIMENT_STANDARD.md), `scripts/generate_paradigm_v2_synthetic.py`, `python/src/paradigm/ml/features.py`.
**Alcance:** especificar una función generadora con **ground truth** auditable y escenarios de señal/drift/missingness.
**Fuera de alcance:** cambiar CSV actuales, entrenar modelos, o reemplazar el generador v1 en este PR/doc.

El generador v1 (`status_roll` i.i.d.) sirve para BI/mart; **no** para evaluar predictivo honesto. v2 existe para el ciclo **Observe → Predict → Explain → Decide → Learn** con claims etiquetados (predictivo ≠ causal ≠ impacto simulado).

---

## 1. Propósito científico del generador

Permitir experimentos de no-show (y downstream de explicación / simulación / política) sobre un dataset donde:

1. Existe una **probabilidad verdadera** \(p_i = P(Y_i=1 \mid X_i^{\text{pre}}, u_i)\) conocida por fila.
2. La **dificultad** (fuerza de señal, ruido, drift) es un hiperparámetro reproducible.
3. Se puede **validar** si un pipeline recupera efectos, calibra \(p\), y no usa leakage.
4. Queda explícito qué claims son legítimos: rendimiento predictivo vs interpretación vs causalidad (esta última solo si el escenario introduce un tratamiento asignado con diseño).

**No** pretende imitar un centro clínico real ni justificar ROI clínico. Es un **banco de prueba metodológico** con verdad generadora versionada.

---

## 2. Unidad de análisis y punto de decisión

| Campo | Definición v2 |
|-------|----------------|
| **Unidad** | Una cita (`appointment_id`), igual que el modelo actual |
| **Universo ML** | Filas con status final ∈ {ATTENDED, NO_SHOW}; CANCELLED se genera aparte (proceso competidor) y se excluye del binario, alineado a `dataset.py` |
| **Target binario** | \(Y = 1\) si NO_SHOW, \(0\) si ATTENDED |
| **Punto de decisión** | **Post-booking, pre-cita**: toda feature usada para \(p_i\) debe ser observable en `booking_ts` (o derivable solo con información ≤ booking / agenda ya fijada) |
| **Horizonte de uso** | Score usable desde la reserva hasta D−1 (mismo \(p\) salvo escenarios de drift/política que muevan coeficientes en el tiempo) |

Agenda (`appointment_start`, especialidad, proveedor) se considera **conocida al reservar** (como hoy). Historial de no-shows del paciente/proveedor solo con citas **estrictamente anteriores**.

---

## 3. Variables disponibles antes del turno

### 3.1 Observables al booking (candidatas a entrar en \(p\))

| Variable | Notas |
|----------|--------|
| `lead_time_days` | Derivada de booking vs appointment |
| `booking_channel_id` | WEB / PHONE / RECEPTION |
| `appointment_hour`, `appointment_dow`, `appointment_month` | Agenda fijada |
| `booking_hour` | Hora de la reserva |
| `specialty_id`, `provider_id` | Proveedor → especialidad (como v1) |
| `coverage_id` | **Alineada al paciente** en v2 (corrige inconsistencia v1) |
| `age_band`, `sex` | Demografía del paciente |
| `patient_prior_appt_count`, `patient_prior_no_show_count/rate` | Solo pasado |
| `provider_prior_appt_count`, `provider_prior_no_show_count/rate` | Solo pasado |
| `reminder_sent` (nuevo) | Flag predecisional: recordatorio SMS/app enviado ≥24h antes |
| `is_repeat_patient` (derivable) | `patient_prior_appt_count > 0` |

### 3.2 Latentes (verdad generadora; no necesariamente en CSV “operativo”)

| Latente | Uso |
|---------|-----|
| `patient_propensity_u` | Efecto aleatorio paciente \(u_p \sim \mathcal{N}(0,\sigma_u^2)\) |
| `provider_effect_v` | Efecto fijo/aleatorio por proveedor \(v_j\) |
| `true_p` | \(p_i\) usada para muestrear \(Y\) |
| `logit_eta` | Predictor lineal antes del sigmoid |

Opcional en artefacto de verdad (no feature del modelo “ciego”): `true_p`, `eta`, `u_p`, `v_j`.

---

## 4. Variables post-outcome excluidas de \(p\) y del feature set predictivo

| Variable | Motivo |
|----------|--------|
| `appointment_status_id` / `status_code` | Es el outcome (o lo determina) |
| `cancellation_ts`, `cancellation_reason_id` | Solo si canceló; post-decisión / proceso competidor |
| Toda `fact_billing_line` | Condicionada a status (leakage) |
| Montos, `billing_status_id`, delays de cobro | Post-outcome |
| Cualquier agregado que incluya la cita actual | Leakage temporal |
| Labels futuros del mismo paciente en la misma fecha | Leakage |

Billing y cancelación **sí** pueden generarse después para demos BI, con la misma regla: nunca entran a features de clasificación no-show.

---

## 5. Fórmula probabilística propuesta

Proceso en dos etapas para el status operativo:

1. Con probabilidad \(\pi_{\text{cancel}}\) (posiblemente con efectos suaves propios) → CANCELLED (fuera del binario ML).
2. Si no cancela: \(Y \sim \mathrm{Bernoulli}(p)\), \(Y=1\) → NO_SHOW, \(Y=0\) → ATTENDED.

### 5.1 Probabilidad de no-show

\[
p_i = \sigma(\eta_i),\quad
\sigma(z)=\frac{1}{1+e^{-z}}
\]

\[
\begin{aligned}
\eta_i =\;&
\underbrace{\beta_0}_{\text{intercepto}}
+ \underbrace{\beta_L\, f_L(L_i)}_{\text{lead (no lineal)}}
+ \underbrace{\boldsymbol{\beta}_C^{\top} \mathbf{1}_{C_i}}_{\text{canal}}
+ \underbrace{\beta_H\, g_H(H_i)}_{\text{hora}}
+ \underbrace{\boldsymbol{\beta}_D^{\top} \mathbf{1}_{D_i}}_{\text{DOW}}
+ \underbrace{\boldsymbol{\beta}_S^{\top} \mathbf{1}_{S_i}}_{\text{especialidad}}
+ \underbrace{\beta_R\, R_i}_{\text{recurrencia / prior rate}}
\\
&+ \underbrace{\beta_{\text{cov}}\, \mathbf{1}_{\text{Particular},i}}_{\text{cobertura}}
+ \underbrace{\beta_{\text{rem}}\, M_i}_{\text{recordatorio}}
+ \underbrace{\beta_{L\times C}\, f_L(L_i)\, \mathbf{1}_{C_i=\text{WEB}}}_{\text{interacción}}
+ \underbrace{u_{p(i)}}_{\text{propensión paciente}}
+ \underbrace{v_{j(i)}}_{\text{efecto profesional}}
+ \underbrace{s(t_i)}_{\text{estacionalidad}}
+ \underbrace{\varepsilon_i}_{\text{ruido}}
\end{aligned}
\]

donde \(L_i\) = lead time (días), \(C_i\) canal, \(H_i\) hora, \(D_i\) día de semana, \(S_i\) especialidad, \(R_i\) = `patient_prior_no_show_rate` (o 0 si sin historia), \(M_i\in\{0,1\}\) recordatorio, \(t_i\) fecha de cita.

### 5.2 Componentes

| Componente | Forma propuesta (default) |
|------------|---------------------------|
| **Intercepto** \(\beta_0\) | Calibrado para tasa elegible objetivo \(\bar p \approx 0.12\)–\(0.15\) tras integrar sobre el diseño de \(X\) |
| **Lead no lineal** | \(f_L(L)=\log(1+L)\) o spline suave; \(\beta_L>0\) (más lead → más riesgo) |
| **Canal** | Contrastes: WEB \(>\) PHONE \(>\) RECEPTION (referencia) |
| **Hora** | \(g_H(H)=\mathbf{1}_{H\ge 15}\) (tarde) o efecto cuadrático suave en \(H\) |
| **DOW** | Lunes/viernes levemente peores que martes–jueves |
| **Especialidad** | Efectos acotados \(\lvert\beta_S\rvert \le \delta_S\) (evitar separabilidad) |
| **Recurrencia / historial** | \(\beta_R>0\) sobre prior rate; opcional término \(\beta_{R0}\mathbf{1}_{\text{primera visita}}\) |
| **Cobertura** | Ligero aumento si Particular (o PAMI), resto 0 |
| **Recordatorio** | \(\beta_{\text{rem}}<0\) (protege) |
| **Interacción** | Lead alto × WEB aumenta riesgo (olvidos / menor fricción de compromiso) |
| **Propensión paciente** | \(u_p \sim \mathcal{N}(0,\sigma_u^2)\), fija por paciente en el dataset |
| **Profesional** | \(v_j \sim \mathcal{N}(0,\sigma_v^2)\) o efectos fijos acotados |
| **Estacionalidad** | \(s(t)=\alpha_m \sin(2\pi m/12)+\alpha_w \mathbf{1}_{\text{semana previa feriado synth}}\) |
| **Ruido** | \(\varepsilon_i \sim \mathcal{N}(0,\sigma_\varepsilon^2)\); escala la **dificultad** junto con \(\lvert\beta\rvert\) |

**Escalado de señal:** un factor global `signal_scale` \(\kappa \in \{0.35, 1.0, 1.8\}\) multiplica todos los \(\beta\) (no \(\beta_0\), no necesariamente \(u,v\) por separado — ver escenarios). Así se pasan de señal débil → fuerte sin reescribir la fórmula.

**Cancelación (competidor, simple):** \(\pi_{\text{cancel}} \approx 0.15\)–\(0.20\) con dependencia débil opcional de lead (más lead → algo más de cancelación temprana); independiente de \(Y\) condicional a no cancelar.

---

## 6. Variables candidatas (detalle)

| Variable | En \(p\)? | Dirección esperada (default) | Notas |
|----------|-----------|------------------------------|-------|
| Lead time | Sí | ↑ riesgo con \(L\) | Efecto principal no lineal |
| Canal | Sí | WEB ↑, RECEPTION ↓ | Categórico |
| Hora | Sí | Tarde ↑ | Predecisional (agenda) |
| Día de semana | Sí | Lun/Vie ↑ | Suave |
| Especialidad | Sí | Heterogénea acotada | No debe dominar |
| Recurrencia | Sí (vía priors / flag) | Primera visita levemente ↑ o neutro | Evitar confundir con prior rate |
| Historial previo | Sí | Prior no-show rate ↑ | Generado por \(u_p\) + pasado real |
| Cobertura | Sí | Particular ↑ leve | Misma cobertura paciente=cita |
| Recordatorio | Sí (nuevo campo) | ↓ riesgo | Asignación: Bernoulli o política por canal |
| Edad / sexo | Opcional débil | Efectos menores o 0 en default | Evitar estereotipos fuertes sin necesidad científica |
| `booking_hour` | Opcional débil / 0 | — | Puede quedar como distractor controlado |
| Provider prior rates | Indirecto | Vía \(v_j\) + historia | No hace falta coeficiente extra si \(v_j\) existe |

---

## 7. Escenarios configurables

| ID | Nombre | Qué cambia | Uso |
|----|--------|------------|-----|
| `signal_weak` | Señal débil | \(\kappa=0.35\), \(\sigma_\varepsilon\) alto | Techo AUC bajo; stress de overfit |
| `signal_moderate` | Señal moderada (**default**) | \(\kappa=1.0\) | Banco principal Predict/Explain |
| `signal_strong` | Señal fuerte | \(\kappa=1.8\), \(\sigma_\varepsilon\) bajo | Sanity: el pipeline **debe** superar baseline; no para “ganar AUC” de portfolio |
| `drift_temporal` | Drift | \(\beta(t)=\beta+\Delta\cdot\mathbf{1}_{t\ge t^\*}\) o rotación de \(\beta_L,\beta_C\) a mitad de calendario | Tests de estabilidad / monitoreo |
| `policy_change` | Cambio de política | A partir de \(t^\*\): `reminder_sent` pasa de 20% a 70% (o solo WEB) | Impacto simulado / Evaluate políticas (no causal sin diseño) |
| `missingness` | Missingness | MAR/MCAR en `coverage_id`, `reminder_sent`, rare gaps en `booking_ts` hour | Robustez de imputación / pipelines |
| `anomalies` | Anomalías | 1–3% filas con lead imposible corregido a 0, duplicados suaves, billing gaps extremos | Data quality Observe |

Los escenarios pueden **componerse** (`signal_moderate` + `drift_temporal`) vía lista `active_scenarios` en config.

---

## 8. Parámetros configurables y defaults

```text
generator_version: "2.0.0-design"
seed: 42
n_appointments: 2000          # ↑ vs 520 para estimar efectos
n_patients: 180
n_providers: 8
date_start: "2024-01-02"
date_end: "2025-12-31"
pi_cancel: 0.18
target_eligible_noshow_rate: 0.13   # para calibrar β0
signal_scale (κ): 1.0
sigma_u: 0.45                 # propensión paciente
sigma_v: 0.25                 # efecto profesional
sigma_eps: 0.35               # ruido iid
reminder_base_rate: 0.35
beta_0: calibrado (no hardcode ciego)
beta_L: 0.35                  # sobre f_L = log1p(L)
beta_C: {WEB: 0.40, PHONE: 0.15, RECEPTION: 0.0}
beta_H_late: 0.25             # H >= 15
beta_D: {Mon: 0.15, Fri: 0.12, else: 0}
beta_S: acotado |β|<=0.30
beta_R: 0.80                  # prior no-show rate
beta_first_visit: 0.10
beta_cov_particular: 0.20
beta_rem: -0.55
beta_LxWEB: 0.20
alpha_season_month: 0.12
drift_start: null | "2025-01-01"
drift_delta: {beta_L: +0.25, WEB: +0.15}
policy_reminder_after: null | "2025-01-01"
policy_reminder_rate: 0.70
missingness: {coverage_id: 0.0, reminder_sent: 0.0}  # >0 en escenario
anomaly_rate: 0.0
```

Valores exactos de \(\beta_0\) y \(\beta_S\) se fijan en implementación por **calibración Monte Carlo** bajo el diseño de \(X\) hasta alcanzar `target_eligible_noshow_rate` ± tolerancia.

---

## 9. Restricciones (anti-patrones)

| Riesgo | Restricción |
|--------|-------------|
| **Leakage** | \(p\) y features solo con §3; billing/cancel/status fuera; priors con `shift(1)` |
| **Target trivial** | Prohibido \(p\in\{0,1\}\); clip \(p\in[0.02, 0.85]\); \(\sigma_\varepsilon\) mínimo > 0 en todos los escenarios salvo debug explícito |
| **Separabilidad artificial** | \(\lvert\beta\rvert\) acotados; `signal_strong` no puede usar un único feature determinístico; AUC empírico objetivo por escenario (ver §12) |
| **Efectos imposibles** | No usar facturación para \(Y\); no usar cancelación como feature del binario; cobertura cita = paciente; recordatorio solo si `booking_ts` permite envío (≥1 día de lead o flag N/A) |
| **Desbalance extremo** | Tasa elegible objetivo en \([0.08, 0.25]\); rechazar generación si tasa ∉ rango tras calibración |
| **Confundir claims** | Guardar verdad no implica que SHAP = causal; escenarios de política etiquetar claim `simulated_impact` |

---

## 10. Verdad generadora a guardar por dataset

Artefacto sugerido: `data/synthetic_v2/<run_tag>/generator_truth.json` (+ opcional `appointment_truth.parquet` con `true_p`, `eta`, `u`, `v`).

Campos mínimos:

| Campo | Contenido |
|-------|-----------|
| `generator_version` | SemVer del código generador |
| `generated_at` | ISO-8601 UTC |
| `seed` | Entero |
| `config` | Copia íntegra de `generator_config.json` |
| `coefficients` | \(\beta_0\), vectores \(\beta\), \(\kappa\), clips |
| `effects` | Tablas `provider_id → v_j`, resumen de \(u_p\) (media/var; o hash del vector) |
| `interactions` | Lista explícita (p. ej. `lead_x_web`) |
| `seasonality` | Parámetros \(s(t)\) |
| `noise` | \(\sigma_u,\sigma_v,\sigma_\varepsilon\) |
| `calibration` | Tasa objetivo vs tasa realizada; n elegible |
| `scenario_ids` | Escenarios activos |
| `data_fingerprint` | SHA-256 de facts/dims emitidos |
| `excluded_from_features` | Lista post-outcome |

Opcional por fila (no mezclar con features del modelo “ciego”): `true_p_i`, `eta_i`.

---

## 11. Métricas de validación del dataset

| Métrica | Definición operativa | Claim |
|---------|----------------------|-------|
| **Tasa objetivo** | \(\hat\pi = \bar Y\) en elegibles; \(|\hat\pi - \pi^\*| \le 0.02\) | Observe |
| **Estabilidad** | Dos generaciones mismo seed → mismos fingerprints | Reproducibilidad |
| **Señal por variable** | MI / odds ratio empírico vs dirección de \(\beta\); correlación `true_p`–feature | Observe / Predict |
| **Calibración de \(p\) verdadera** | ECE o Brier de `true_p` vs \(Y\) (debe ser bueno por construcción Bernoulli) | Sanity del generador |
| **Reproducibilidad** | Hash config + seed + version → hash datos | Learn |
| **Drift** | En escenario drift: \(\Delta\) tasa o \(\Delta\) OR de lead/canal pre/post \(t^\*\) detectable | Observe |
| **Recuperación parcial de efectos** | Regresión logística de \(Y\sim X\) (o de `true_p` transformado): signos de \(\hat\beta_L,\hat\beta_{\text{rem}},\hat\beta_{\text{WEB}}\) coinciden con verdad en señal moderate/strong | Predict (diagnóstico, no causal) |

AUC de un modelo ML **no** es métrica de aceptación del dataset (es del experimento); sí lo es el AUC de **ranking por `true_p`** (debe ser alto: ~0.75–0.90 según \(\kappa\)).

---

## 12. Criterios de aceptación para aprobar una generación

Una generación v2 se **aprueba** solo si cumple todos:

1. `generator_truth.json` completo (§10) y `generator_config.json` versionado juntos.
2. Fingerprints de CSV/parquet coinciden con los declarados en truth.
3. Misma `(version, seed, config)` reproduce bit-a-bit (o tolerancia numérica documentada solo si hay paralelismo; preferir serial).
4. Tasa elegible de no-show dentro de \(\pi^* \pm 0.02\) y dentro de \([0.08, 0.25]\).
5. `true_p` clipado; ningún \(p\in\{0,1\}\); Brier(`true_p`, \(Y\)) ≤ Brier(tasa constante) − margen mínimo según escenario.
6. AUC de ranking por `true_p` en rango por escenario:
   - weak: ≈ 0.58–0.68
   - moderate: ≈ 0.68–0.80
   - strong: ≈ 0.80–0.90
   (fuera de rango → recalibrar \(\kappa/\sigma_\varepsilon\), no “aceptar y callar”).
7. Ninguna columna post-outcome en el manifiesto de features predictivas.
8. Cobertura cita = paciente en ≥ 99% filas (el resto solo si escenario anomalías lo declara).
9. En `drift_temporal` / `policy_change`: efecto pre/post \(t^\*\) detectable en OR o tasa según lo configurado.
10. Documentado el claim permitido: dataset para **predictivo sintético**; no evidencia clínica.

---

## Pseudocódigo de la función generadora

```text
function generate_paradigm_v2(config):
    rng ← Generator(config.seed)
    patients ← sample_patients(rng, config)           # incluye u_p ~ N(0, σ_u²)
    providers ← sample_providers(rng, config)         # incluye v_j
    calibrate β0 so E[σ(η)] ≈ config.target_rate under design X

    appointments ← []
    for i in 1..config.n_appointments:
        x ← sample_predecisional_context(rng, patients, providers, config)
            # lead, channel, schedule, coverage=patient.coverage,
            # reminder ~ Bern(r_t) possibly after policy_change date
        hist ← priors_from_past_only(appointments, x.patient_id, x.provider_id)

        if drift_active(x.date, config):
            β ← β + config.drift_delta
        else:
            β ← config.coefficients

        η ← β0
            + κ * β_L * log1p(x.lead)
            + κ * β_C[x.channel]
            + κ * β_H * 1{x.hour ≥ 15}
            + κ * β_D[x.dow]
            + κ * β_S[x.specialty]
            + κ * β_R * hist.patient_prior_noshow_rate
            + κ * β_first * 1{hist.patient_prior_appt == 0}
            + κ * β_cov * 1{x.coverage == Particular}
            + κ * β_rem * x.reminder_sent
            + κ * β_LxWEB * log1p(x.lead) * 1{x.channel == WEB}
            + u[x.patient] + v[x.provider]
            + s(x.date)
            + ε ~ N(0, σ_ε²)

        p ← clip(sigmoid(η), 0.02, 0.85)

        if rng.random() < pi_cancel(x, config):
            status ← CANCELLED; fill cancellation fields
        else if rng.random() < p:
            status ← NO_SHOW
        else:
            status ← ATTENDED

        appointments.append(row(x, hist, status, true_p=p, eta=η))
        maybe_add_billing_after_status(...)   # never feeds p

    apply_missingness_and_anomalies(appointments, config)
    write_dims_facts(appointments)
    write_generator_truth(...)
    validate_acceptance_criteria(...)        # fail closed
    return dataset_paths
```

---

## Ejemplo de `generator_config.json`

```json
{
  "generator_version": "2.0.0-design",
  "seed": 42,
  "n_appointments": 2000,
  "n_patients": 180,
  "n_providers": 8,
  "date_start": "2024-01-02",
  "date_end": "2025-12-31",
  "pi_cancel": 0.18,
  "target_eligible_noshow_rate": 0.13,
  "signal_scale": 1.0,
  "noise": {
    "sigma_u": 0.45,
    "sigma_v": 0.25,
    "sigma_eps": 0.35
  },
  "reminder_base_rate": 0.35,
  "coefficients": {
    "beta_L": 0.35,
    "beta_C": { "WEB": 0.40, "PHONE": 0.15, "RECEPTION": 0.0 },
    "beta_H_late": 0.25,
    "beta_D": { "Mon": 0.15, "Tue": 0.0, "Wed": 0.0, "Thu": 0.0, "Fri": 0.12 },
    "beta_S_max_abs": 0.30,
    "beta_R": 0.80,
    "beta_first_visit": 0.10,
    "beta_cov_particular": 0.20,
    "beta_rem": -0.55,
    "beta_lead_x_web": 0.20,
    "alpha_season_month": 0.12
  },
  "p_clip": [0.02, 0.85],
  "active_scenarios": ["signal_moderate"],
  "drift": {
    "enabled": false,
    "start": "2025-01-01",
    "delta": { "beta_L": 0.25, "WEB": 0.15 }
  },
  "policy_change": {
    "enabled": false,
    "start": "2025-01-01",
    "reminder_rate_after": 0.70
  },
  "missingness": {
    "coverage_id": 0.0,
    "reminder_sent": 0.0
  },
  "anomaly_rate": 0.0,
  "output_dir": "data/synthetic_v2/moderate_default",
  "write_row_truth": true
}
```

---

## Tablas de cierre

### Variable | Tipo de efecto | Dirección esperada | Rango | Riesgo metodológico

| Variable | Tipo de efecto | Dirección esperada | Rango | Riesgo metodológico |
|----------|----------------|--------------------|-------|---------------------|
| Intercepto \(\beta_0\) | Nivel base | Calibra tasa ~13% | logit | Mal calibrado → desbalance extremo |
| Lead \(f_L(L)\) | No lineal | ↑ | \(\kappa\cdot\beta_L\cdot\log(1+L)\) | Señal fácil si \(\beta_L\) enorme |
| Canal | Categórico | WEB ↑ | OR acotados | Confundir con lead si correlación de diseño alta |
| Hora tarde | Lineal (indicador) | ↑ | \(\beta_H\in[0,0.5]\kappa\) | Efecto “mágico” si solo tardes fallan |
| DOW | Categórico suave | Lun/Vie ↑ | pequeño | Estacionalidad confundida con drift |
| Especialidad | Categórico acotado | Heterogénea | \(\lvert\beta_S\rvert\le 0.3\kappa\) | Separabilidad por especialidad |
| Prior no-show rate | Lineal | ↑ | \(\beta_R\sim 0.8\kappa\) | Leakage si no hay shift |
| Primera visita | Indicador | ↑ leve | pequeño | Colineal con prior=0 |
| Cobertura Particular | Indicador | ↑ leve | pequeño | Estigma sintético si se overclaim |
| Recordatorio | Tratamiento predecisional | ↓ | \(\beta_{\text{rem}}<0\) | Causal solo con asignación explícita |
| Lead × WEB | Interacción | ↑ | moderada | Modelos lineales la pierden |
| \(u_p\) paciente | Latente | Heterogeneidad | \(\sigma_u\sim 0.45\) | Overfit a ID si se usa patient_id raw |
| \(v_j\) profesional | Latente / fijo | Heterogeneidad | \(\sigma_v\sim 0.25\) | Idem provider_id |
| Estacionalidad \(s(t)\) | Cíclica | Variable | \(\alpha\) pequeño | Falso drift |
| \(\varepsilon\) | Ruido iid | — | \(\sigma_\varepsilon>0\) | \(\sigma\to 0\) ⇒ target casi determinista |

### Escenario | Señal | Drift | Missingness | Uso recomendado

| Escenario | Señal | Drift | Missingness | Uso recomendado |
|-----------|-------|-------|-------------|-----------------|
| `signal_weak` | Débil (\(\kappa=0.35\)) | No | No | Stress overfit; techo bajo |
| `signal_moderate` | Moderada (\(\kappa=1\)) | No | No | Default Predict / Explain |
| `signal_strong` | Fuerte (\(\kappa=1.8\)) | No | No | Sanity de pipeline; no portfolio “AUC alto” |
| `drift_temporal` | Moderada | Sí (coef post \(t^\*\)) | No | Monitoreo / estabilidad temporal |
| `policy_change` | Moderada | Política de reminder | No | Simulación de impacto / políticas |
| `missingness` | Moderada | No | Sí (MAR/MCAR) | Robustez de features / QA |
| `anomalies` | Moderada | No | Opcional | Observe / data quality |
| `moderate+drift` | Moderada | Sí | No | Aprendizaje continuo sintético |

---

## Relación con el stack actual

- Features del modelo actual (`features.py`) son un **subconjunto** de §3; v2 añade `reminder_sent` y alinea cobertura.
- El generador v1 permanece para demos hasta migrar; v2 debe vivir en ruta aparte (`data/synthetic_v2/...`) para no silently invalidar hashes del MVP.
- Todo experimento sobre v2 debe declarar en el contrato de 18 campos (`EXPERIMENT_STANDARD.md`) el `generator_version`, escenario y que el éxito puede ser metodológico (recuperación de signos / calibración), no solo AUC.

**Próximo paso (fuera de este documento):** implementar el generador tras aprobación del diseño, con tests de aceptación §12 y sin tocar `data/synthetic/` v1 salvo decisión explícita de deprecación.
