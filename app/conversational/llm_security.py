"""Seguridad LLM: validación SQL y rate limiting."""

from __future__ import annotations

import os
import re
import time
from collections import deque
from threading import Lock

from app.conversational.sql_engine import is_safe_sql

_RATE_LOCK = Lock()
_RATE_BUCKETS: dict[str, deque[float]] = {}

_DEFAULT_MAX_PER_MINUTE = 10
_DEFAULT_WINDOW_SEC = 60


def _max_requests_per_minute() -> int:
    raw = os.getenv("PARADIGM_LLM_RATE_LIMIT", str(_DEFAULT_MAX_PER_MINUTE))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_PER_MINUTE


def check_rate_limit(bucket_id: str = "app") -> tuple[bool, str | None]:
    """
    Rate limiting en memoria (por sesión/proceso).
    Retorna (allowed, error_message).
    """
    limit = _max_requests_per_minute()
    now = time.monotonic()
    window = _DEFAULT_WINDOW_SEC

    with _RATE_LOCK:
        bucket = _RATE_BUCKETS.setdefault(bucket_id, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False, f"Límite de {limit} consultas LLM por minuto alcanzado. Reintentá en unos segundos."
        bucket.append(now)
    return True, None


def reset_rate_limit(bucket_id: str = "app") -> None:
    """Útil en tests."""
    with _RATE_LOCK:
        _RATE_BUCKETS.pop(bucket_id, None)


def validate_llm_sql(sql: str) -> tuple[bool, str | None]:
    """
    Validación reforzada post-LLM.
    Solo una sentencia SELECT/WITH; sin DDL/DML.
    """
    if not sql or not str(sql).strip():
        return False, "SQL vacío."

    cleaned = str(sql).strip()
    if not is_safe_sql(cleaned):
        return False, "Solo se permiten consultas SELECT o WITH."

    # Una sola sentencia (evita inyección con '; DELETE ...')
    body = cleaned.rstrip(";").strip()
    if ";" in body:
        return False, "Una sola sentencia SQL permitida."

    # Bloquear subconsultas peligrosas obvias en strings (defensa en profundidad)
    if re.search(r"\b(PRAGMA|ATTACH|DETACH|VACUUM)\b", body, re.IGNORECASE):
        return False, "Palabra clave SQL no permitida."

    return True, None


def sanitize_llm_sql(sql: str) -> str | None:
    """Valida y retorna SQL limpio, o None si no es seguro."""
    ok, _ = validate_llm_sql(sql)
    if not ok:
        return None
    return str(sql).strip().rstrip(";").strip()
