"""Análisis profundo de notebooks Jupyter vía LLM + fallback heurístico."""

from __future__ import annotations

import logging
from typing import Any

from app.config.llm_config import get_llm_settings, is_llm_available
from app.conversational.llm_logging import log_llm_interaction
from app.conversational.llm_security import check_rate_limit
from app.conversational.llm_service import LLMService, _parse_json_response
from app.conversational.notebook_parser import ParsedNotebook, build_llm_context, extract_headings
from app.conversational.types import NotebookAnalysisResult

logger = logging.getLogger(__name__)

NOTEBOOK_SYSTEM_PROMPT = """Sos un revisor senior de notebooks analíticos en Paradigm.
Tu audiencia incluye analistas de datos y stakeholders no técnicos.

REGLAS:
1. Basate SOLO en el contenido del notebook provisto (markdown, código, outputs, errores, gráficos).
2. Sé específico: citá secciones, patrones de código u outputs cuando sea posible.
3. Si falta evidencia, decilo y bajá la confianza.
4. El resumen en lenguaje sencillo debe evitar jerga técnica.
5. Respondé ÚNICAMENTE con un objeto JSON válido (sin markdown, sin texto extra).

Campos JSON requeridos:
- executive_summary (string): 2-4 oraciones de alto nivel
- positives (array de strings): aspectos bien resueltos
- improvements (array de strings): áreas de mejora concretas
- critical_issues (array de strings): problemas graves (errores, huecos metodológicos); array vacío si no hay
- prioritized_recommendations (array de strings): acciones ordenadas por impacto
- advanced_suggestions (array de strings): mejoras técnicas opcionales (refactor, tests, reproducibilidad)
- plain_language_summary (string): resumen para alguien sin background técnico (3-5 oraciones)
- confidence (string): uno de "high", "medium", "low"
- sources (array de strings): secciones o celdas del notebook usadas como evidencia
"""

NOTEBOOK_QUERY = "Analizar notebook completo y generar informe estructurado."


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _notebook_result_to_log(result: NotebookAnalysisResult) -> dict[str, Any]:
    return {
        "insight": result.executive_summary,
        "recommendation": "; ".join(result.prioritized_recommendations[:3]),
        "business_impact": "Medio",
        "confidence": result.confidence,
        "sources": list(result.sources),
        "used_llm": result.used_llm,
        "fallback_reason": result.fallback_reason,
    }


def _normalize_notebook_payload(
    payload: dict[str, Any],
    parsed: ParsedNotebook,
    *,
    used_llm: bool = True,
    fallback_reason: str | None = None,
) -> NotebookAnalysisResult:
    sources = _as_str_list(payload.get("sources"))
    if not sources:
        headings = extract_headings(parsed)
        if headings:
            sources = [f"sección:{h}" for h in headings[:5]]

    critical = _as_str_list(payload.get("critical_issues"))
    return NotebookAnalysisResult(
        filename=parsed.filename,
        title=parsed.title,
        executive_summary=str(payload.get("executive_summary", "")).strip()
        or "Informe generado a partir del contenido del notebook.",
        positives=_as_str_list(payload.get("positives")),
        improvements=_as_str_list(payload.get("improvements")),
        critical_issues=critical,
        prioritized_recommendations=_as_str_list(payload.get("prioritized_recommendations")),
        advanced_suggestions=_as_str_list(payload.get("advanced_suggestions")),
        plain_language_summary=str(payload.get("plain_language_summary", "")).strip()
        or str(payload.get("executive_summary", "")).strip(),
        used_llm=used_llm,
        fallback_reason=fallback_reason,
        confidence=str(payload.get("confidence", "medium")).lower(),
        sources=sources,
    )


def _heuristic_notebook_analysis(
    parsed: ParsedNotebook,
    *,
    reason: str | None = None,
) -> NotebookAnalysisResult:
    """Fallback estructural cuando el LLM no está disponible."""
    headings = extract_headings(parsed)
    positives: list[str] = []
    improvements: list[str] = []
    critical: list[str] = []
    recommendations: list[str] = []
    advanced: list[str] = []

    if parsed.n_markdown > 0:
        positives.append(
            f"Incluye {parsed.n_markdown} celda(s) markdown que documentan el análisis."
        )
    if headings:
        positives.append(f"Estructura clara con secciones: {', '.join(headings[:4])}.")
    if parsed.n_with_plot > 0:
        positives.append(f"Contiene {parsed.n_with_plot} visualización(es) generada(s) en el notebook.")
    if parsed.n_with_output > 0:
        positives.append(f"{parsed.n_with_output} celda(s) de código con outputs ejecutados.")

    if parsed.n_code == 0:
        improvements.append("No hay celdas de código — el notebook es solo narrativa.")
    elif parsed.n_markdown == 0:
        improvements.append("Falta documentación markdown; agregá contexto de negocio y conclusiones.")
    elif parsed.n_markdown < parsed.n_code * 0.3:
        improvements.append(
            "Poca narrativa respecto al código; equilibrá explicaciones entre bloques analíticos."
        )

    code_without_output = sum(
        1
        for c in parsed.cells
        if c.cell_type == "code" and not c.outputs_summary and not c.has_plot and not c.has_error
    )
    if code_without_output:
        improvements.append(
            f"{code_without_output} celda(s) de código sin output visible — ejecutalas o explicá por qué."
        )

    if parsed.n_errors:
        critical.append(
            f"{parsed.n_errors} celda(s) con error de ejecución — revisá dependencias, datos y variables."
        )
        for cell in parsed.cells:
            if cell.has_error and cell.outputs_summary:
                critical.append(f"Celda {cell.index}: {cell.outputs_summary[:200]}")

    if not critical:
        critical = []

    if parsed.n_errors:
        recommendations.append("Corregir celdas con error antes de compartir el notebook.")
    if code_without_output:
        recommendations.append("Re-ejecutar el notebook de arriba a abajo (Run All) y guardar outputs.")
    if parsed.n_markdown == 0:
        recommendations.append("Agregar secciones de objetivo, metodología y conclusiones en markdown.")
    recommendations.append("Validar que las conclusiones estén respaldadas por los outputs mostrados.")

    advanced.append("Extraer funciones repetidas a un módulo `.py` importable para reproducibilidad.")
    advanced.append("Versionar datos de entrada o documentar su procedencia en el notebook.")
    if parsed.n_with_plot:
        advanced.append("Agregar títulos y etiquetas descriptivas a todos los gráficos.")

    if not positives:
        positives.append("El notebook fue parseado correctamente y está listo para revisión manual.")

    title_ref = parsed.title or parsed.filename
    exec_summary = (
        f"Notebook «{title_ref}» con {parsed.cell_count} celdas "
        f"({parsed.n_markdown} markdown, {parsed.n_code} código). "
    )
    if parsed.n_errors:
        exec_summary += f"Se detectaron {parsed.n_errors} error(es) de ejecución que requieren atención."
    elif parsed.n_with_plot:
        exec_summary += "Incluye visualizaciones y outputs ejecutados."
    else:
        exec_summary += "Revisar ejecución completa y documentación narrativa."

    plain = (
        f"Este informe revisa el notebook «{title_ref}». "
        f"Tiene {parsed.cell_count} secciones/celdas en total. "
    )
    if parsed.n_errors:
        plain += (
            "Hay partes del análisis que fallaron al ejecutarse; conviene corregirlas antes de usar los resultados. "
        )
    elif parsed.n_with_plot:
        plain += "El trabajo incluye gráficos que ayudan a comunicar hallazgos. "
    plain += (
        "Las recomendaciones priorizan mejorar claridad, ejecución correcta y conclusiones accionables."
    )

    return NotebookAnalysisResult(
        filename=parsed.filename,
        title=parsed.title,
        executive_summary=exec_summary,
        positives=positives,
        improvements=improvements,
        critical_issues=critical,
        prioritized_recommendations=recommendations,
        advanced_suggestions=advanced,
        plain_language_summary=plain,
        used_llm=False,
        fallback_reason=reason or "LLM no disponible",
        confidence="low",
        sources=["fallback:heuristic", f"notebook:{parsed.filename}"],
    )


def _analyze_with_llm(service: LLMService, parsed: ParsedNotebook) -> NotebookAnalysisResult:
    settings = service.settings
    notebook_context = build_llm_context(parsed)
    rag_context = service.retrieve_context(NOTEBOOK_QUERY) if settings.rag_enabled else ""

    user_prompt = "\n\n".join(
        part
        for part in [
            f"ARCHIVO: {parsed.filename}",
            f"CONTENIDO DEL NOTEBOOK:\n{notebook_context}",
            f"CONTEXTO RAG (referencia):\n{rag_context}" if rag_context else "",
            "Generá el informe JSON solicitado.",
        ]
        if part
    )

    raw, elapsed_ms = service.complete(NOTEBOOK_SYSTEM_PROMPT, user_prompt)
    payload = _parse_json_response(raw)
    result = _normalize_notebook_payload(payload, parsed, used_llm=True)
    if rag_context and not any(s.startswith("RAG") for s in result.sources):
        result.sources.append(f"RAG ({settings.rag_top_k} chunks)")

    log_llm_interaction(
        settings,
        operation="analyze_notebook",
        query=NOTEBOOK_QUERY,
        success=True,
        used_llm=True,
        duration_ms=elapsed_ms,
        response=_notebook_result_to_log(result),
        raw_response=raw,
        sources=result.sources,
    )
    return result


def analyze_notebook(parsed: ParsedNotebook) -> NotebookAnalysisResult:
    """
    Genera informe estructurado de un notebook parseado.
    Usa LLM + RAG si está disponible; si no, fallback heurístico.
    """
    settings = get_llm_settings()

    if not is_llm_available(settings):
        result = _heuristic_notebook_analysis(parsed, reason="LLM no disponible")
        log_llm_interaction(
            settings,
            operation="analyze_notebook",
            query=NOTEBOOK_QUERY,
            success=False,
            used_llm=False,
            duration_ms=0,
            response=_notebook_result_to_log(result),
            error="LLM no disponible",
            sources=result.sources,
        )
        return result

    allowed, msg = check_rate_limit()
    if not allowed:
        result = _heuristic_notebook_analysis(parsed, reason=msg)
        log_llm_interaction(
            settings,
            operation="analyze_notebook",
            query=NOTEBOOK_QUERY,
            success=False,
            used_llm=False,
            duration_ms=0,
            response=_notebook_result_to_log(result),
            error=msg,
            sources=result.sources,
        )
        return result

    service = LLMService(settings)
    try:
        return _analyze_with_llm(service, parsed)
    except Exception as exc:
        logger.warning("analyze_notebook LLM falló (%s); usando fallback heurístico.", exc)
        result = _heuristic_notebook_analysis(parsed, reason=str(exc))
        log_llm_interaction(
            settings,
            operation="analyze_notebook",
            query=NOTEBOOK_QUERY,
            success=False,
            used_llm=False,
            duration_ms=0,
            response=_notebook_result_to_log(result),
            error=str(exc),
            sources=result.sources,
        )
        return result
