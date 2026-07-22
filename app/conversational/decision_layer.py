"""Capa conversacional Decide: consultas sobre paradigm.prescriptive (sin UI).

Respuestas determinísticas basadas en la salida estructurada del motor.
Diferencia dato / predicción / simulación / recomendación.
No afirma causalidad.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

# Garantiza import de paradigm.* aunque el CWD no tenga python/src en PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "python" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from paradigm.io.paths import REPO_ROOT
from paradigm.prescriptive import PrescriptiveConfig, PrescriptiveResult, run_prescriptive_engine

DecisionIntent = Literal[
    "who_to_contact",
    "why_priority",
    "which_policy",
    "cost_sensitivity",
    "not_decision",
]

# Afirmaciones causales falsas a evitar (no bloquear negaciones educativas).
FORBIDDEN_CAUSAL_PATTERNS = (
    r"\bcausa el no-?show\b",
    r"\bcausan el no-?show\b",
    r"\bprovoca(n)? el no-?show\b",
    r"\befecto causal (comprobado|demostrado|validado|probado)\b",
    r"\bgarantiza(r|mos)? (que|el|la)\b",
    r"\baumenta la probabilidad porque\b",
)

CLAIM_LABELS = {
    "dato": "DATO",
    "prediccion": "PREDICCIÓN",
    "simulacion": "SIMULACIÓN",
    "recomendacion": "RECOMENDACIÓN",
}


@dataclass
class DecisionAnswer:
    intent: DecisionIntent
    insight: str
    recommendation: str
    explanation: str
    evidence: dict[str, Any]
    sources: list[str]
    confidence: str = "medium"
    business_impact: str = "Medio"


def classify_decision_intent(query: str) -> DecisionIntent:
    """Clasifica consultas Decide (heurístico, sin LLM)."""
    q = (query or "").lower().strip()
    if not q:
        return "not_decision"

    why = any(
        x in q
        for x in (
            "por qué",
            "porque",
            "por que",
            "prioridad",
            "esta cita",
            "esta recomend",
            "explica",
            "explicá",
            "motivo",
        )
    ) and any(
        x in q
        for x in ("cita", "prioridad", "apt-", "recomend", "intervenir", "contact")
    )
    # "por qué esta cita tiene prioridad"
    if why or re.search(r"apt-?\d+", q, flags=re.I):
        if any(x in q for x in ("por qué", "porque", "por que", "explica", "explicá", "motivo", "prioridad")):
            return "why_priority"

    if any(
        x in q
        for x in (
            "qué política",
            "que politica",
            "política se",
            "politica se",
            "qué regla",
            "que regla",
            "política usada",
            "politica usada",
            "policy",
        )
    ):
        return "which_policy"

    if any(
        x in q
        for x in (
            "aumenta el costo",
            "sube el costo",
            "si aumenta",
            "si sube",
            "sensibilidad",
            "costo de intervención",
            "costo de intervencion",
            "qué cambia si",
            "que cambia si",
            "what if",
            "cost sensitivity",
        )
    ):
        return "cost_sensitivity"

    if any(
        x in q
        for x in (
            "a quién",
            "a quien",
            "quiénes",
            "quienes",
            "contactar",
            "contactá",
            "prioriz",
            "intervenir",
            "intervención",
            "intervencion",
            "hoy",
            "recomenda",
            "ranking",
            "lista de citas",
        )
    ):
        return "who_to_contact"

    return "not_decision"


def extract_appointment_id(query: str) -> str | None:
    m = re.search(r"(APT-?\d+)", query or "", flags=re.I)
    if not m:
        return None
    raw = m.group(1).upper().replace("APT", "APT")
    if raw.startswith("APT") and not raw.startswith("APT-"):
        raw = "APT-" + raw[3:]
    return raw


def find_latest_risk_predictions(
    *,
    dataset_id: str = "signal_moderate_seed42",
    runs_root: Path | None = None,
) -> Path:
    root = runs_root or (REPO_ROOT / "ml" / "experiments" / "runs")
    matches = sorted(root.glob(f"*no_show_v2_{dataset_id}"))
    if not matches:
        raise FileNotFoundError(f"No hay run de riesgo para {dataset_id}")
    path = matches[-1] / "predictions" / "test_predictions.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def load_prescriptive_context(
    *,
    config: PrescriptiveConfig | None = None,
    predictions: pd.DataFrame | None = None,
    dataset_id: str = "signal_moderate_seed42",
    runs_root: Path | None = None,
) -> PrescriptiveResult:
    """Carga predicciones de riesgo y ejecuta el motor (determinístico)."""
    cfg = config or PrescriptiveConfig()
    if predictions is None:
        path = find_latest_risk_predictions(dataset_id=dataset_id, runs_root=runs_root)
        predictions = pd.read_csv(path)
    return run_prescriptive_engine(predictions, cfg)


def _assert_no_false_causality(text: str) -> None:
    low = text.lower()
    for pat in FORBIDDEN_CAUSAL_PATTERNS:
        if re.search(pat, low):
            raise AssertionError(f"Respuesta contiene afirmación causal prohibida: {pat}")


def _format_claims(blocks: list[tuple[str, str]]) -> str:
    lines = []
    for kind, text in blocks:
        label = CLAIM_LABELS.get(kind, kind.upper())
        lines.append(f"[{label}] {text}")
    return "\n".join(lines)


def answer_who_to_contact(result: PrescriptiveResult, *, top_n: int = 10) -> DecisionAnswer:
    recs = result.recommendations
    intervened = recs[recs["recommended_action"] == "intervene"].head(top_n)
    lines = []
    for _, row in intervened.iterrows():
        lines.append(
            f"- {row['appointment_id']}: riesgo={row['risk_score']:.2f}, "
            f"uplift={row['uplift']:.3f}, ENV={row['expected_net_value']:.2f}, "
            f"prioridad={int(row['priority'])}"
        )
    unc = result.uncertainty_summary
    insight = _format_claims(
        [
            (
                "dato",
                f"Capacidad={result.capacity}; intervenidos={result.n_intervened}; "
                f"política={result.policy_used}.",
            ),
            (
                "prediccion",
                "Scores de riesgo (y uplift estimado/asumido) del hold-out de predicciones.",
            ),
            (
                "recomendacion",
                f"Contactar primero estas {len(intervened)} citas (ranking bajo política "
                f"`{result.policy_used}`). Es una recomendación operativa, "
                f"no un mecanismo verificado del no-show.",
            ),
            (
                "dato",
                f"Incertidumbre: uplift_disponible={unc.get('fraction_with_real_uplift')}, "
                f"calidad_uplift={unc.get('uplift_quality')}, "
                f"fuente_uplift={unc.get('uplift_source')}.",
            ),
        ]
    )
    if lines:
        insight += "\n\nTop contactos:\n" + "\n".join(lines)
    explanation = (
        "Ranking generado por paradigm.prescriptive a partir de predicciones; "
        "la acción prioriza contacto bajo capacidad, sin atribuir un mecanismo "
        "verificado del outcome."
    )
    evidence = {
        "policy_used": result.policy_used,
        "capacity": result.capacity,
        "n_intervened": result.n_intervened,
        "top_ids": intervened["appointment_id"].tolist(),
        "uncertainty_summary": unc,
        "policy_selection": result.policy_selection,
    }
    ans = DecisionAnswer(
        intent="who_to_contact",
        insight=insight,
        recommendation=f"Priorizá el top-{len(intervened)} listado bajo política `{result.policy_used}`.",
        explanation=explanation,
        evidence=evidence,
        sources=[
            "prescriptive:engine",
            "claim:dato",
            "claim:prediccion",
            "claim:recomendacion",
        ],
        confidence="medium" if unc.get("fraction_with_real_uplift", 0) < 1 else "high",
        business_impact="Alto",
    )
    _assert_no_false_causality(ans.insight + ans.recommendation + ans.explanation)
    return ans


def answer_why_priority(
    result: PrescriptiveResult,
    *,
    appointment_id: str | None,
) -> DecisionAnswer:
    recs = result.recommendations
    if appointment_id is None:
        # Usar la de mayor prioridad
        row = recs[recs["priority"] > 0].sort_values("priority").head(1)
        if row.empty:
            row = recs.head(1)
        appointment_id = str(row.iloc[0]["appointment_id"])
    else:
        row = recs[recs["appointment_id"].astype(str).str.upper() == appointment_id.upper()]
        if row.empty:
            insight = _format_claims(
                [
                    (
                        "dato",
                        f"No se encontró la cita `{appointment_id}` en las recomendaciones actuales.",
                    ),
                    (
                        "recomendacion",
                        "Verificá el ID (formato APT-#####) o regenerá el motor prescriptivo.",
                    ),
                ]
            )
            return DecisionAnswer(
                intent="why_priority",
                insight=insight,
                recommendation="Elegí un appointment_id presente en el ranking.",
                explanation="Lookup fallido en salida estructurada del motor.",
                evidence={"appointment_id": appointment_id, "found": False},
                sources=["prescriptive:engine", "claim:dato"],
                confidence="low",
            )
    r = row.iloc[0]
    unc = r["uncertainty"] if isinstance(r["uncertainty"], dict) else {}
    insight = _format_claims(
        [
            (
                "dato",
                f"Cita `{r['appointment_id']}` | política=`{r['policy_used']}` | "
                f"acción=`{r['recommended_action']}` | prioridad={int(r['priority'])}.",
            ),
            (
                "prediccion",
                f"Riesgo={float(r['risk_score']):.3f}; uplift={float(r['uplift']):.3f}; "
                f"valor neto esperado (ENV)={float(r['expected_net_value']):.3f}.",
            ),
            (
                "dato",
                f"Incertidumbre: margen_a_0.5={unc.get('risk_margin_to_0_5')}, "
                f"uplift_available={unc.get('uplift_available')}, "
                f"uplift_source={unc.get('uplift_source')}.",
            ),
            (
                "recomendacion",
                str(r["explanation"])
                + " Esto prioriza contacto bajo la política vigente; "
                "no interpreta el score como mecanismo del no-show.",
            ),
        ]
    )
    evidence = {
        "appointment_id": str(r["appointment_id"]),
        "row": {
            "recommended_action": r["recommended_action"],
            "risk_score": float(r["risk_score"]),
            "uplift": float(r["uplift"]),
            "expected_net_value": float(r["expected_net_value"]),
            "priority": int(r["priority"]),
            "policy_used": r["policy_used"],
            "uncertainty": unc,
        },
    }
    ans = DecisionAnswer(
        intent="why_priority",
        insight=insight,
        recommendation="Usá la explicación del motor; no interpretes el score como mecanismo del outcome.",
        explanation="Explicación derivada de la fila estructurada de paradigm.prescriptive.",
        evidence=evidence,
        sources=["prescriptive:engine", "claim:prediccion", "claim:recomendacion"],
        confidence="medium",
        business_impact="Medio",
    )
    _assert_no_false_causality(ans.insight + ans.recommendation)
    return ans


def answer_which_policy(result: PrescriptiveResult) -> DecisionAnswer:
    sel = result.policy_selection
    cfg = result.config
    insight = _format_claims(
        [
            (
                "dato",
                f"Política operativa=`{result.policy_used}`. "
                f"Motivo: {sel.get('reason')}.",
            ),
            (
                "dato",
                f"Parámetros: B={cfg.get('benefit_per_avoided')}, "
                f"C={cfg.get('intervention_cost')}, "
                f"capacidad={result.capacity}, "
                f"uplift_quality={cfg.get('uplift_quality')} "
                f"(umbral={cfg.get('uplift_quality_threshold')}).",
            ),
            (
                "prediccion",
                "La política elige cómo rankear predicciones (riesgo/uplift/ENV); "
                "no valida un mecanismo del no-show.",
            ),
            (
                "recomendacion",
                f"Se interviene a {result.n_intervened} citas bajo esta política.",
            ),
        ]
    )
    evidence = {
        "policy_used": result.policy_used,
        "policy_selection": sel,
        "config": cfg,
        "comparison_keys": list(result.comparison.keys()),
    }
    ans = DecisionAnswer(
        intent="which_policy",
        insight=insight,
        recommendation="Documentá la política en el run; cambiá calidad/costo para otras reglas.",
        explanation="Regla de select_operating_policy + salida del motor.",
        evidence=evidence,
        sources=["prescriptive:engine", "claim:dato", "claim:recomendacion"],
        confidence="high",
    )
    _assert_no_false_causality(ans.insight)
    return ans


def answer_cost_sensitivity(
    predictions: pd.DataFrame,
    base_config: PrescriptiveConfig,
    *,
    cost_multipliers: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0, 20.0),
) -> DecisionAnswer:
    """What-if: varía costo de intervención y reporta política / n_intervened."""
    base_c = float(base_config.intervention_cost)
    rows: list[dict[str, Any]] = []
    for m in cost_multipliers:
        cfg = PrescriptiveConfig(
            benefit_per_avoided=base_config.benefit_per_avoided,
            intervention_cost=base_c * m,
            max_interventions=base_config.max_interventions,
            max_intervention_fraction=base_config.max_intervention_fraction,
            uplift_quality=base_config.uplift_quality,
            assumed_ate=base_config.assumed_ate,
            random_seed=base_config.random_seed,
            risk_column=base_config.risk_column,
        )
        res = run_prescriptive_engine(predictions, cfg)
        rows.append(
            {
                "cost": cfg.intervention_cost,
                "multiplier": m,
                "policy": res.policy_used,
                "n_intervened": res.n_intervened,
                "capacity": res.capacity,
                "reason": res.policy_selection.get("reason"),
            }
        )
    lines = [
        f"- C={r['cost']:.2f} (×{r['multiplier']}): política=`{r['policy']}`, "
        f"intervenidos={r['n_intervened']}"
        for r in rows
    ]
    insight = _format_claims(
        [
            (
                "simulacion",
                "What-if sobre el costo de intervención (mismo ranking de predicciones).",
            ),
            (
                "dato",
                f"Costo base={base_c}. Escenarios:\n" + "\n".join(lines),
            ),
            (
                "recomendacion",
                "Si el costo supera B×ATE de referencia, la regla cae a `none` "
                "(no contactar). Esto es sensibilidad de política, no un mecanismo "
                "verificado del outcome.",
            ),
        ]
    )
    ans = DecisionAnswer(
        intent="cost_sensitivity",
        insight=insight,
        recommendation="Revisá el umbral económico antes de operar con costos reales.",
        explanation="Simulación determinística re-ejecutando paradigm.prescriptive.",
        evidence={"scenarios": rows, "base_cost": base_c},
        sources=["prescriptive:engine", "claim:simulacion", "claim:recomendacion"],
        confidence="medium",
        business_impact="Alto",
    )
    _assert_no_false_causality(ans.insight + ans.recommendation)
    return ans


def answer_decision_query(
    query: str,
    *,
    predictions: pd.DataFrame | None = None,
    config: PrescriptiveConfig | None = None,
    dataset_id: str = "signal_moderate_seed42",
    runs_root: Path | None = None,
) -> DecisionAnswer | None:
    """
    Si la consulta es Decide, responde; si no, retorna None (dejar pasar a LLM/heurística).
    """
    intent = classify_decision_intent(query)
    if intent == "not_decision":
        return None

    cfg = config or PrescriptiveConfig()
    if predictions is None:
        path = find_latest_risk_predictions(dataset_id=dataset_id, runs_root=runs_root)
        predictions = pd.read_csv(path)

    if intent == "cost_sensitivity":
        return answer_cost_sensitivity(predictions, cfg)

    result = run_prescriptive_engine(predictions, cfg)
    if intent == "who_to_contact":
        return answer_who_to_contact(result)
    if intent == "why_priority":
        return answer_why_priority(result, appointment_id=extract_appointment_id(query))
    if intent == "which_policy":
        return answer_which_policy(result)
    return None


def decision_answer_to_analyst_fields(answer: DecisionAnswer) -> dict[str, Any]:
    """Mapea a campos de AnalystResult (+ evidence en raw/explanation)."""
    explanation = (
        answer.explanation
        + "\n\n--- Evidencia ---\n"
        + json.dumps(answer.evidence, ensure_ascii=False, indent=2, default=str)
    )
    return {
        "sql": None,
        "insight": answer.insight,
        "recommendation": answer.recommendation,
        "business_impact": answer.business_impact,
        "confidence": answer.confidence,
        "sources": list(answer.sources) + [f"decision_intent:{answer.intent}"],
        "used_llm": False,
        "fallback_reason": None,
        "explanation": explanation,
        "raw_response": json.dumps(
            {"intent": answer.intent, "evidence": answer.evidence},
            ensure_ascii=False,
            default=str,
        ),
    }
