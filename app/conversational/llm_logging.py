"""Logging estructurado de interacciones LLM (JSONL)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.llm_config import LLMSettings, get_llm_settings

logger = logging.getLogger(__name__)

LOG_FILENAME = "llm_interactions.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_log_path(settings: LLMSettings | None = None) -> Path:
    cfg = settings or get_llm_settings()
    return cfg.rag_persist_dir.parent / LOG_FILENAME


def estimate_tokens(*texts: str | None) -> int:
    """Aproximación liviana: ~4 caracteres por token (inglés/código)."""
    total_chars = sum(len(t) for t in texts if t)
    return max(1, total_chars // 4) if total_chars else 0


def analyst_result_response_payload(result: Any) -> dict[str, Any]:
    """Serializa AnalystResult o dict para el log."""
    if isinstance(result, dict):
        return {
            "sql": result.get("sql"),
            "insight": result.get("insight"),
            "recommendation": result.get("recommendation"),
            "business_impact": result.get("business_impact"),
            "confidence": result.get("confidence"),
            "sources": result.get("sources", []),
            "used_llm": result.get("used_llm"),
            "fallback_reason": result.get("fallback_reason"),
        }
    return {
        "sql": getattr(result, "sql", None),
        "insight": getattr(result, "insight", None),
        "recommendation": getattr(result, "recommendation", None),
        "business_impact": getattr(result, "business_impact", None),
        "confidence": getattr(result, "confidence", None),
        "sources": list(getattr(result, "sources", []) or []),
        "used_llm": getattr(result, "used_llm", False),
        "fallback_reason": getattr(result, "fallback_reason", None),
    }


def log_llm_interaction(
    settings: LLMSettings,
    *,
    operation: str,
    query: str,
    success: bool,
    used_llm: bool,
    duration_ms: float | None = None,
    response: Any | None = None,
    raw_response: str | None = None,
    error: str | None = None,
    sources: list[str] | None = None,
    tokens_prompt: int | None = None,
    tokens_completion: int | None = None,
) -> None:
    if not settings.log_interactions:
        return

    response_payload = analyst_result_response_payload(response) if response is not None else {}
    tokens_in = tokens_prompt if tokens_prompt is not None else estimate_tokens(query)
    tokens_out = tokens_completion if tokens_completion is not None else estimate_tokens(
        raw_response,
        response_payload.get("insight"),
        response_payload.get("sql"),
    )

    from app.conversational.llm_logging import utc_now_iso

    entry: dict[str, Any] = {
        "ts": utc_now_iso(),
        "operation": operation,
        "query": query,
        "provider": settings.provider,
        "model": settings.model,
        "success": success,
        "used_llm": used_llm,
        "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        "tokens_approx": {
            "prompt": tokens_in,
            "completion": tokens_out,
            "total": tokens_in + tokens_out,
        },
        "response": response_payload,
        "raw_response": (raw_response[:8000] if raw_response else None),
        "error": error,
        "sources": sources or response_payload.get("sources") or [],
    }

    log_path = get_log_path(settings)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("No se pudo escribir log LLM: %s", exc)


def read_log_entries(limit: int = 50, settings: LLMSettings | None = None) -> list[dict[str, Any]]:
    """Lee las últimas entradas del JSONL (más recientes primero)."""
    log_path = get_log_path(settings)
    if not log_path.is_file():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    entries: list[dict[str, Any]] = []
    for line in reversed(lines[-limit * 2 :]):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= limit:
            break
    return entries
