"""Servicio minimo de Paradigm Copilot.

No ejecuta codigo. Las correcciones son propuestas y toda salida requiere revision humana.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.conversational import llm_service
from app.conversational.copilot_contract import CopilotRequest, CopilotResponse, CopilotTask


class CopilotServiceError(RuntimeError):
    """Error del servicio Copilot ante proveedor no disponible o respuesta invalida."""


_SYSTEM_PROMPT = """Sos un companero tecnico de Data Science para Paradigm.
No ejecutes codigo, SQL, notebooks ni comandos.
No afirmes que una propuesta fue probada, validada o verificada.
Diferencia con claridad errores sintacticos, logicos, de datos y conceptuales.
Todas las correcciones son propuestas y requieren revision humana.
Responde unicamente con JSON valido, sin markdown ni texto extra.

JSON requerido:
{
  "summary": "string",
  "explanation": ["string"],
  "issues": ["string"],
  "suggested_fix": "string o null",
  "risks": ["string"],
  "requires_review": true
}
"""

_TASK_INSTRUCTIONS: dict[CopilotTask, str] = {
    CopilotTask.EXPLAIN_SQL: (
        "Explica la consulta SQL paso a paso, su objetivo, filtros, agregaciones y supuestos. "
        "No propongas ejecucion."
    ),
    CopilotTask.REVIEW_SQL: (
        "Revisa la consulta SQL y senala problemas potenciales de sintaxis, logica, semantica, costo o ambiguedad. "
        "Si propones cambios, marcalos como propuesta."
    ),
    CopilotTask.EXPLAIN_PYTHON: (
        "Explica el codigo Python, su flujo, dependencias implicitas, efectos esperados y puntos fragiles. "
        "No afirmes resultados de ejecucion."
    ),
    CopilotTask.ANALYZE_ERROR: (
        "Analiza el error reportado y clasificalo explicitamente como sintactico, logico, de datos o conceptual. "
        "Relaciona el error con el contenido dado y no inventes ejecucion."
    ),
    CopilotTask.PROPOSE_FIX: (
        "Propone una correccion minima y razonada para el contenido dado. "
        "Aclara riesgos, supuestos y que la correccion debe revisarse manualmente."
    ),
}

_REQUIRED_KEYS = {
    "summary",
    "explanation",
    "issues",
    "suggested_fix",
    "risks",
    "requires_review",
}


def _build_user_prompt(request: CopilotRequest) -> str:
    lines = [
        f"TASK: {request.task.value}",
        f"INSTRUCCIONES ESPECIFICAS: {_TASK_INSTRUCTIONS[request.task]}",
        "CONTENT:",
        request.content,
    ]
    if request.context:
        lines.extend(["CONTEXT:", request.context])
    if request.error_message:
        lines.extend(["ERROR_MESSAGE:", request.error_message])
    lines.append("Devuelve exclusivamente el JSON requerido.")
    return "\n\n".join(lines)


def _parse_json_payload(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        raise CopilotServiceError("Respuesta vacia del modelo.")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise CopilotServiceError("Respuesta JSON invalida.") from None
        try:
            payload = json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise CopilotServiceError("Respuesta JSON invalida.") from exc
    if not isinstance(payload, dict):
        raise CopilotServiceError("La respuesta JSON debe ser un objeto.")
    return payload


def _require_string(value: Any, key: str) -> str:
    if not isinstance(value, str):
        raise CopilotServiceError(f"El campo '{key}' debe ser string.")
    return value


def _require_string_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CopilotServiceError(f"El campo '{key}' debe ser lista de strings.")
    return list(value)


def _validate_payload(payload: dict[str, Any]) -> CopilotResponse:
    missing = sorted(_REQUIRED_KEYS.difference(payload))
    if missing:
        raise CopilotServiceError(f"Faltan claves requeridas: {', '.join(missing)}")

    summary = _require_string(payload["summary"], "summary")
    explanation = _require_string_list(payload["explanation"], "explanation")
    issues = _require_string_list(payload["issues"], "issues")
    suggested_fix = payload["suggested_fix"]
    if suggested_fix is not None and not isinstance(suggested_fix, str):
        raise CopilotServiceError("El campo 'suggested_fix' debe ser string o null.")
    risks = _require_string_list(payload["risks"], "risks")
    if not isinstance(payload["requires_review"], bool):
        raise CopilotServiceError("El campo 'requires_review' debe ser boolean.")

    return CopilotResponse(
        summary=summary,
        explanation=explanation,
        issues=issues,
        suggested_fix=suggested_fix,
        risks=risks,
        requires_review=True,
    )


def _invoke_model(system_prompt: str, user_prompt: str) -> str:
    allowed, message = llm_service.check_rate_limit()
    if not allowed:
        raise CopilotServiceError(message or "Rate limit alcanzado.")

    try:
        llm = llm_service.get_llm()
    except llm_service.LLMNotAvailableError as exc:
        raise CopilotServiceError(str(exc)) from exc

    if llm_service.SystemMessage is None or llm_service.HumanMessage is None:
        raise CopilotServiceError("Dependencias de mensajeria LLM no disponibles.")

    response = llm.invoke(
        [
            llm_service.SystemMessage(content=system_prompt),
            llm_service.HumanMessage(content=user_prompt),
        ]
    )
    content = response.content
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


def generate_copilot_response(request: CopilotRequest) -> CopilotResponse:
    """Genera una respuesta estructurada sin ejecutar codigo y con revision humana obligatoria."""

    user_prompt = _build_user_prompt(request)
    raw_text = _invoke_model(_SYSTEM_PROMPT, user_prompt)
    payload = _parse_json_payload(raw_text)
    return _validate_payload(payload)