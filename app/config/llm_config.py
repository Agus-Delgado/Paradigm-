"""Configuración del Conversational Analyst (LLM + RAG)."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from app.config.theme import REPO_ROOT

LLMProvider = Literal["ollama", "groq", "openai", "grok", "disabled"]

_DEFAULT_OLLAMA_BASE = "http://localhost:11434"
_DEFAULT_GROK_BASE = "https://api.x.ai/v1"

_DOTENV_LOADED = False


def load_dotenv_if_present() -> None:
    """Carga `.env` desde la raíz del repo (idempotente)."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    _DOTENV_LOADED = True


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_provider(raw: str | None) -> LLMProvider:
    value = (raw or "ollama").strip().lower()
    if value in ("ollama", "groq", "openai", "grok", "disabled"):
        return value  # type: ignore[return-value]
    return "ollama"


@dataclass(frozen=True)
class LLMSettings:
    provider: LLMProvider = "ollama"
    model: str = "llama3.2"
    embedding_model: str = "nomic-embed-text"
    temperature: float = 0.1
    max_tokens: int = 2048
    ollama_base_url: str = _DEFAULT_OLLAMA_BASE
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    grok_api_key: str | None = None
    grok_base_url: str = _DEFAULT_GROK_BASE
    rag_enabled: bool = True
    rag_top_k: int = 5
    rag_persist_dir: Path = field(default_factory=lambda: REPO_ROOT / "data" / "processed" / "rag_index")
    log_interactions: bool = True
    rag_corpus_paths: tuple[Path, ...] = field(default_factory=tuple)

    def is_api_provider(self) -> bool:
        return self.provider in ("groq", "openai", "grok")

    def active_api_key(self) -> str | None:
        if self.provider == "groq":
            return self.groq_api_key
        if self.provider == "openai":
            return self.openai_api_key
        if self.provider == "grok":
            return self.grok_api_key
        return None


def _default_rag_corpus_paths() -> tuple[Path, ...]:
    paths: list[Path] = [
        REPO_ROOT / "docs" / "data_dictionary.md",
        REPO_ROOT / "docs" / "metrics.md",
    ]
    samples = REPO_ROOT / "sql" / "samples"
    if samples.is_dir():
        paths.extend(sorted(samples.glob("*.sql")))
    return tuple(paths)


def get_llm_settings() -> LLMSettings:
    """Lee configuración LLM/RAG desde variables de entorno (con defaults)."""
    load_dotenv_if_present()

    provider = _normalize_provider(os.getenv("PARADIGM_LLM_PROVIDER"))
    rag_dir = Path(os.getenv("PARADIGM_RAG_PERSIST_DIR", str(REPO_ROOT / "data" / "processed" / "rag_index")))

    return LLMSettings(
        provider=provider,
        model=os.getenv("PARADIGM_LLM_MODEL", "llama3.2").strip(),
        embedding_model=os.getenv("PARADIGM_EMBEDDING_MODEL", "nomic-embed-text").strip(),
        temperature=_env_float("PARADIGM_LLM_TEMPERATURE", 0.1),
        max_tokens=_env_int("PARADIGM_LLM_MAX_TOKENS", 2048),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE).strip().rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        grok_api_key=os.getenv("GROK_API_KEY") or None,
        grok_base_url=os.getenv("GROK_BASE_URL", _DEFAULT_GROK_BASE).strip().rstrip("/"),
        rag_enabled=_env_bool("PARADIGM_RAG_ENABLED", True),
        rag_top_k=_env_int("PARADIGM_RAG_TOP_K", 5),
        rag_persist_dir=rag_dir,
        log_interactions=_env_bool("PARADIGM_LLM_LOG_INTERACTIONS", True),
        rag_corpus_paths=_default_rag_corpus_paths(),
    )


def _ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def is_llm_available(settings: LLMSettings | None = None) -> bool:
    """
    Comprueba si el proveedor configurado está listo para usarse.
    No lanza excepciones — retorna False si no hay LLM disponible.
    """
    load_dotenv_if_present()
    cfg = settings or get_llm_settings()

    if cfg.provider == "disabled":
        return False
    if cfg.provider == "ollama":
        return _ollama_reachable(cfg.ollama_base_url)
    if cfg.provider == "groq":
        return bool(cfg.groq_api_key and cfg.groq_api_key.strip())
    if cfg.provider == "openai":
        return bool(cfg.openai_api_key and cfg.openai_api_key.strip())
    if cfg.provider == "grok":
        return bool(cfg.grok_api_key and cfg.grok_api_key.strip())
    return False


def get_active_model_id(settings: LLMSettings | None = None) -> str:
    """Devuelve el identificador de modelo activo según el proveedor."""
    cfg = settings or get_llm_settings()
    return cfg.model
