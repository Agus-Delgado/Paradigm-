"""Servicio LLM + RAG para el Conversational Analyst híbrido."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.llm_config import LLMSettings, get_llm_settings, is_llm_available
from app.conversational.llm_logging import log_llm_interaction
from app.conversational.llm_security import check_rate_limit, sanitize_llm_sql, validate_llm_sql
from app.conversational.nl_to_sql import _generate_sql_heuristic
from app.conversational.sql_engine import TABLE_NAME
from app.conversational.types import Domain

logger = logging.getLogger(__name__)

_FAISS_SUBDIR = "faiss_index"
_MANIFEST_FILE = "corpus_manifest.json"
_DEFAULT_HF_EMBEDDING = "sentence-transformers/all-MiniLM-L6-v2"

SYSTEM_PROMPT = """Sos un analista senior de operaciones ambulatorias en Paradigm.
Tu rol es interpretar datos sintéticos de consultorios (citas, no-shows, facturación, KPIs).

REGLAS ESTRICTAS:
1. Solo afirmá lo que esté respaldado por el CONTEXTO RAG, el SCHEMA del dataset o RESULTADOS SQL provistos.
2. Si no hay evidencia suficiente, decilo explícitamente y bajá la confianza.
3. Para SQL: SOLO consultas de lectura (SELECT o WITH). Tabla única: `data`. Sin INSERT/UPDATE/DELETE/DROP.
4. Usá nombres de columnas exactos del schema cuando generes SQL.
5. Sé conservador: priorizá precisión sobre creatividad.
6. Respondé ÚNICAMENTE con un objeto JSON válido (sin markdown, sin texto extra).

Campos JSON requeridos:
- sql (string o null): consulta SQLite si aplica
- insight (string): hallazgo narrativo conciso en español
- recommendation (string): acción concreta y priorizable
- business_impact (string): uno de "Alto", "Medio", "Bajo"
- confidence (string): uno de "high", "medium", "low"
- sources (array de strings): fuentes usadas (archivos RAG, columnas, filas)

EJEMPLOS FEW-SHOT:

Pregunta: "¿Cuál es la tasa de no-show por especialidad?"
SQL:
SELECT specialty_name AS segmento,
       AVG(CASE WHEN status_code = 'NO_SHOW' THEN 1.0 ELSE 0.0 END) AS no_show_rate,
       COUNT(*) AS filas
FROM data
GROUP BY specialty_name
ORDER BY no_show_rate DESC
LIMIT 20
Insight: Cardiología concentra la mayor tasa de no-show del período según los datos disponibles.
Recommendation: Implementar recordatorio activo 48h antes para las especialidades con tasa superior al promedio.
business_impact: Alto
confidence: medium
sources: ["sql/samples/01_no_show_by_specialty.sql", "columnas: specialty_name, status_code"]

Pregunta: "Comparar ingreso neto por canal de reserva"
SQL:
SELECT channel_code AS segmento,
       AVG(net_revenue) AS promedio,
       COUNT(*) AS filas
FROM data
GROUP BY channel_code
ORDER BY promedio DESC
LIMIT 20
Insight: El canal telefónico muestra menor ingreso promedio por cita que el portal web en el subset analizado.
Recommendation: Revisar script de confirmación y política de overbooking en canal Teléfono.
business_impact: Medio
confidence: medium
sources: ["columnas: channel_code, net_revenue"]

Pregunta: "¿Hay brecha entre citas atendidas y facturación?"
SQL:
SELECT COUNT(*) AS attended_no_billing
FROM data
WHERE status_code = 'ATTENDED' AND (billing_status IS NULL OR billing_status = 'PENDING')
Insight: Existe un subconjunto de citas atendidas sin línea de facturación cerrada — posible brecha operativa.
Recommendation: Ejecutar conciliación semanal atención vs facturación y escalar casos >7 días.
business_impact: Alto
confidence: low
sources: ["docs/metrics.md", "columnas: status_code, billing_status"]
"""

SQL_SYSTEM_PROMPT = """Sos un experto en SQL SQLite para analytics de operaciones ambulatorias.
Generá SOLO una consulta SELECT o WITH sobre la tabla `data`.
Sin DDL/DML. Sin comentarios SQL en la respuesta.
Respondé ÚNICAMENTE con JSON: {"sql": "...", "explanation": "...", "confidence": "high|medium|low", "sources": ["..."]}
Usá nombres de columnas exactos del schema provisto."""


class LLMNotAvailableError(RuntimeError):
    """El proveedor LLM configurado no está disponible."""


@dataclass
class AnalystResult:
    sql: str | None
    insight: str
    recommendation: str
    business_impact: str
    confidence: str
    sources: list[str] = field(default_factory=list)
    used_llm: bool = False
    fallback_reason: str | None = None
    explanation: str | None = None
    raw_response: str | None = None


def get_llm(settings: LLMSettings | None = None) -> BaseChatModel:
    """Retorna el chat model configurado según el proveedor activo."""
    cfg = settings or get_llm_settings()
    if cfg.provider == "disabled":
        raise LLMNotAvailableError("LLM deshabilitado (PARADIGM_LLM_PROVIDER=disabled).")
    if not is_llm_available(cfg):
        raise LLMNotAvailableError(
            f"Proveedor '{cfg.provider}' no disponible. "
            "Verificá Ollama en ejecución o las API keys en .env."
        )

    if cfg.provider == "ollama":
        return ChatOllama(
            model=cfg.model,
            base_url=cfg.ollama_base_url,
            temperature=cfg.temperature,
            num_predict=cfg.max_tokens,
        )
    if cfg.provider == "groq":
        return ChatGroq(
            model=cfg.model,
            api_key=cfg.groq_api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    if cfg.provider == "openai":
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.openai_api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    if cfg.provider == "grok":
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.grok_api_key,
            base_url=cfg.grok_base_url,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    raise LLMNotAvailableError(f"Proveedor no soportado: {cfg.provider}")


def _utc_now_iso() -> str:
    from app.conversational.llm_logging import utc_now_iso

    return utc_now_iso()


def _rate_limit_or_fallback_insight(
    query: str,
    context_df: pd.DataFrame | None,
    logical_types: dict[str, str] | None,
    settings: LLMSettings,
) -> AnalystResult | None:
    allowed, msg = check_rate_limit()
    if allowed:
        return None
    result = _heuristic_insight_fallback(query, context_df, logical_types)
    result.fallback_reason = msg
    log_llm_interaction(
        settings,
        operation="generate_insights",
        query=query,
        success=False,
        used_llm=False,
        duration_ms=0,
        response=result,
        error=msg,
        sources=result.sources,
    )
    return result


def _corpus_manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            stat = path.stat()
            manifest[str(path)] = f"{stat.st_mtime_ns}:{stat.st_size}"
    return manifest


def _manifest_hash(manifest: dict[str, str]) -> str:
    payload = json.dumps(manifest, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load_corpus_documents(paths: tuple[Path, ...]) -> list[Document]:
    docs: list[Document] = []
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        source_label = path.name
        if path.suffix == ".sql":
            source_label = f"sql/samples/{path.name}"
        for chunk in splitter.split_text(text):
            docs.append(
                Document(
                    page_content=chunk.strip(),
                    metadata={"source": source_label, "path": str(path)},
                )
            )
    return docs


def _build_embeddings(settings: LLMSettings):
    """OllamaEmbeddings si provider=ollama y Ollama responde; si no, HuggingFaceEmbeddings."""
    from app.config.llm_config import _ollama_reachable

    if settings.provider == "ollama" and _ollama_reachable(settings.ollama_base_url):
        try:
            return OllamaEmbeddings(
                model=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )
        except Exception as exc:
            logger.warning("OllamaEmbeddings no disponible (%s); usando HuggingFace.", exc)
    return HuggingFaceEmbeddings(model_name=_DEFAULT_HF_EMBEDDING)


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def _normalize_analyst_payload(payload: dict[str, Any]) -> AnalystResult:
    sources = payload.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    sql_val = payload.get("sql")
    if sql_val is not None and isinstance(sql_val, str):
        safe = sanitize_llm_sql(sql_val)
        sql_val = safe
    return AnalystResult(
        sql=sql_val,
        insight=str(payload.get("insight", "")).strip() or "Sin insight generado.",
        recommendation=str(payload.get("recommendation", "")).strip() or "Revisar datos manualmente.",
        business_impact=str(payload.get("business_impact", "Medio")),
        confidence=str(payload.get("confidence", "low")),
        sources=[str(s) for s in sources],
        used_llm=True,
        explanation=payload.get("explanation"),
        raw_response=None,
    )


def _dataframe_schema_block(df: pd.DataFrame, logical_types: dict[str, str] | None = None) -> str:
    logical_types = logical_types or {}
    lines = [f"Tabla SQLite: `{TABLE_NAME}` · {len(df):,} filas · {len(df.columns)} columnas"]
    for col in df.columns:
        ltype = logical_types.get(col, str(df[col].dtype))
        non_null = int(df[col].notna().sum())
        samples = df[col].dropna().head(3).tolist()
        sample_txt = ", ".join(str(s)[:40] for s in samples) if samples else "—"
        lines.append(f"- {col} ({ltype}, {non_null} no-nulos): ej. {sample_txt}")
    return "\n".join(lines)


def _log_interaction(
    settings: LLMSettings,
    *,
    operation: str,
    query: str,
    success: bool,
    used_llm: bool,
    duration_ms: float | None = None,
    response: AnalystResult | None = None,
    raw_response: str | None = None,
    error: str | None = None,
    sources: list[str] | None = None,
) -> None:
    log_llm_interaction(
        settings,
        operation=operation,
        query=query,
        success=success,
        used_llm=used_llm,
        duration_ms=duration_ms,
        response=response,
        raw_response=raw_response,
        error=error,
        sources=sources,
    )


class LLMService:
    """Orquesta chat LLM, RAG FAISS y respuestas estructuradas."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self._settings = settings or get_llm_settings()
        self._vectorstore: FAISS | None = None
        self._index_dir = self._settings.rag_persist_dir / _FAISS_SUBDIR

    @property
    def settings(self) -> LLMSettings:
        return self._settings

    @property
    def index_dir(self) -> Path:
        return self._index_dir

    def _ensure_vectorstore(self) -> FAISS | None:
        if self._vectorstore is not None:
            return self._vectorstore
        if not self._settings.rag_enabled:
            return None

        manifest = _corpus_manifest(self._settings.rag_corpus_paths)
        if not manifest:
            logger.warning("Corpus RAG vacío — sin documentos indexables.")
            return None

        manifest_path = self._settings.rag_persist_dir / _MANIFEST_FILE
        current_hash = _manifest_hash(manifest)
        index_ready = (
            self._index_dir.is_dir()
            and (self._index_dir / "index.faiss").is_file()
            and manifest_path.is_file()
        )
        if index_ready:
            try:
                stored = json.loads(manifest_path.read_text(encoding="utf-8"))
                if stored.get("hash") == current_hash:
                    embeddings = _build_embeddings(self._settings)
                    self._vectorstore = FAISS.load_local(
                        str(self._index_dir),
                        embeddings,
                        allow_dangerous_deserialization=True,
                    )
                    return self._vectorstore
            except Exception as exc:
                logger.warning("No se pudo cargar índice FAISS existente (%s); reconstruyendo.", exc)

        documents = _load_corpus_documents(self._settings.rag_corpus_paths)
        if not documents:
            return None

        try:
            embeddings = _build_embeddings(self._settings)
            self._vectorstore = FAISS.from_documents(documents, embeddings)
            self._settings.rag_persist_dir.mkdir(parents=True, exist_ok=True)
            self._index_dir.mkdir(parents=True, exist_ok=True)
            self._vectorstore.save_local(str(self._index_dir))
            manifest_path.write_text(
                json.dumps({"hash": current_hash, "files": manifest}, indent=2),
                encoding="utf-8",
            )
            logger.info("Índice FAISS construido en %s (%d chunks)", self._index_dir, len(documents))
        except Exception as exc:
            logger.error("Error construyendo índice FAISS: %s", exc)
            self._vectorstore = None
        return self._vectorstore

    def retrieve_context(self, query: str) -> str:
        """Recupera contexto relevante del corpus (docs + SQL samples) vía FAISS."""
        store = self._ensure_vectorstore()
        if store is None:
            return ""
        try:
            docs = store.similarity_search(query, k=self._settings.rag_top_k)
        except Exception as exc:
            logger.warning("Error en similarity_search: %s", exc)
            return ""

        blocks: list[str] = []
        for doc in docs:
            source = doc.metadata.get("source", "desconocido")
            blocks.append(f"[Fuente: {source}]\n{doc.page_content}")
        return "\n\n---\n\n".join(blocks)

    def _invoke_chat(self, system: str, user: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        llm = get_llm(self._settings)
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        response = llm.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = "".join(str(part) for part in content)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return str(content), elapsed_ms

    def generate_insights(
        self,
        query: str,
        context_df: pd.DataFrame | None = None,
        *,
        logical_types: dict[str, str] | None = None,
        sql_result: pd.DataFrame | None = None,
    ) -> AnalystResult:
        """Orquesta RAG + LLM y devuelve insight estructurado."""
        rag_context = self.retrieve_context(query) if self._settings.rag_enabled else ""
        schema_block = ""
        if context_df is not None and not context_df.empty:
            schema_block = _dataframe_schema_block(context_df, logical_types)

        result_preview = ""
        if sql_result is not None and not sql_result.empty:
            preview = sql_result.head(15).to_string(index=False)
            result_preview = f"Resultados SQL (máx. 15 filas):\n{preview}"

        user_prompt = "\n\n".join(
            part
            for part in [
                f"PREGUNTA DEL USUARIO:\n{query}",
                f"CONTEXTO RAG:\n{rag_context}" if rag_context else "",
                f"SCHEMA DEL DATASET:\n{schema_block}" if schema_block else "",
                result_preview,
                "Respondé con el JSON solicitado.",
            ]
            if part
        )

        try:
            raw, elapsed_ms = self._invoke_chat(SYSTEM_PROMPT, user_prompt)
            payload = _parse_json_response(raw)
            result = _normalize_analyst_payload(payload)
            result.raw_response = raw
            if rag_context and not result.sources:
                result.sources = [f"RAG ({self._settings.rag_top_k} chunks)"]
            _log_interaction(
                self._settings,
                operation="generate_insights",
                query=query,
                success=True,
                used_llm=True,
                duration_ms=elapsed_ms,
                response=result,
                raw_response=raw,
                sources=result.sources,
            )
            return result
        except Exception as exc:
            logger.warning("LLM generate_insights falló (%s); usando fallback heurístico.", exc)
            fallback = _heuristic_insight_fallback(query, context_df, logical_types)
            fallback.fallback_reason = str(exc)
            _log_interaction(
                self._settings,
                operation="generate_insights",
                query=query,
                success=False,
                used_llm=False,
                response=fallback,
                error=str(exc),
                sources=fallback.sources,
            )
            return fallback

    def generate_sql_llm(
        self,
        natural_query: str,
        df: pd.DataFrame,
        logical_types: dict[str, str],
        domain: Domain,
    ) -> AnalystResult:
        """Genera SQL vía LLM + RAG; fallback al motor heurístico si falla."""
        rag_context = self.retrieve_context(natural_query)
        schema_block = _dataframe_schema_block(df, logical_types)

        user_prompt = "\n\n".join(
            [
                f"PREGUNTA EN LENGUAJE NATURAL:\n{natural_query}",
                f"SCHEMA:\n{schema_block}",
                f"CONTEXTO RAG (ejemplos y métricas):\n{rag_context}" if rag_context else "",
                "Generá el JSON con sql, explanation, confidence y sources.",
            ]
        )

        try:
            raw, elapsed_ms = self._invoke_chat(SQL_SYSTEM_PROMPT, user_prompt)
            payload = _parse_json_response(raw)
            sql_text = str(payload.get("sql", "")).strip()
            safe_sql = sanitize_llm_sql(sql_text) if sql_text else None
            if not safe_sql:
                ok, reason = validate_llm_sql(sql_text) if sql_text else (False, "SQL vacío")
                raise ValueError(reason or "SQL generado inválido o no permitido (solo SELECT/WITH).")
            # Re-validación explícita post-sanitización
            if not validate_llm_sql(safe_sql)[0]:
                raise ValueError("SQL no pasó validación de seguridad.")

            result = AnalystResult(
                sql=safe_sql,
                insight=str(payload.get("explanation", "")).strip(),
                recommendation="Ejecutá la consulta y validá resultados antes de decidir acciones.",
                business_impact="Medio",
                confidence=str(payload.get("confidence", "medium")),
                sources=[str(s) for s in (payload.get("sources") or [])],
                used_llm=True,
                explanation=str(payload.get("explanation", "")).strip(),
                raw_response=raw,
            )
            _log_interaction(
                self._settings,
                operation="generate_sql_llm",
                query=natural_query,
                success=True,
                used_llm=True,
                duration_ms=elapsed_ms,
                response=result,
                raw_response=raw,
                sources=result.sources,
            )
            return result
        except Exception as exc:
            logger.warning("LLM generate_sql_llm falló (%s); fallback heurístico.", exc)
            sql_text, explanation = _generate_sql_heuristic(natural_query, df, logical_types, domain)
            result = AnalystResult(
                sql=sql_text,
                insight=explanation,
                recommendation="Consulta generada por motor heurístico — revisá y editá antes de ejecutar.",
                business_impact="Bajo",
                confidence="low",
                sources=["heuristic:nl_to_sql"],
                used_llm=False,
                fallback_reason=str(exc),
                explanation=explanation,
            )
            _log_interaction(
                self._settings,
                operation="generate_sql_llm",
                query=natural_query,
                success=False,
                used_llm=False,
                response=result,
                error=str(exc),
                sources=result.sources,
            )
            return result


def _heuristic_insight_fallback(
    query: str,
    context_df: pd.DataFrame | None,
    logical_types: dict[str, str] | None,
) -> AnalystResult:
    """Fallback mínimo cuando el LLM no está disponible."""
    insight = (
        "El analista LLM no está disponible en este momento. "
        "Usá el SQL Explorer o el motor heurístico para explorar el dataset."
    )
    sources = ["fallback:heuristic"]
    if context_df is not None and not context_df.empty:
        cols = ", ".join(list(context_df.columns)[:8])
        insight += f" Dataset activo: {len(context_df):,} filas. Columnas: {cols}."
        sources.append(f"schema:{len(context_df.columns)}_cols")

    return AnalystResult(
        sql=None,
        insight=insight,
        recommendation="Configurá Ollama o una API key y reintentá, o usá Análisis Guiado determinístico.",
        business_impact="Bajo",
        confidence="low",
        sources=sources,
        used_llm=False,
        fallback_reason="LLM no disponible",
    )


# ── API pública de módulo ───────────────────────────────────────────────────

_default_service: LLMService | None = None


def _get_service() -> LLMService:
    global _default_service
    if _default_service is None:
        _default_service = LLMService()
    return _default_service


def generate_insights(
    query: str,
    context_df: pd.DataFrame | None = None,
    *,
    logical_types: dict[str, str] | None = None,
    sql_result: pd.DataFrame | None = None,
    settings: LLMSettings | None = None,
) -> AnalystResult:
    """Orquesta RAG + LLM (función de conveniencia)."""
    service = LLMService(settings) if settings else _get_service()
    if not is_llm_available(service.settings):
        result = _heuristic_insight_fallback(query, context_df, logical_types)
        _log_interaction(
            service.settings,
            operation="generate_insights",
            query=query,
            success=False,
            used_llm=False,
            response=result,
            error="LLM no disponible",
            sources=result.sources,
        )
        return result
    rate_fallback = _rate_limit_or_fallback_insight(query, context_df, logical_types, service.settings)
    if rate_fallback is not None:
        return rate_fallback
    return service.generate_insights(
        query,
        context_df,
        logical_types=logical_types,
        sql_result=sql_result,
    )


def generate_sql_llm(
    natural_query: str,
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
    *,
    settings: LLMSettings | None = None,
) -> AnalystResult:
    """Genera SQL vía LLM con fallback heurístico (función de conveniencia)."""
    service = LLMService(settings) if settings else _get_service()
    if not is_llm_available(service.settings):
        sql_text, explanation = _generate_sql_heuristic(natural_query, df, logical_types, domain)
        result = AnalystResult(
            sql=sql_text,
            insight=explanation,
            recommendation="Motor heurístico — LLM no disponible.",
            business_impact="Bajo",
            confidence="low",
            sources=["heuristic:nl_to_sql"],
            used_llm=False,
            fallback_reason="LLM no disponible",
            explanation=explanation,
        )
        _log_interaction(
            service.settings,
            operation="generate_sql_llm",
            query=natural_query,
            success=False,
            used_llm=False,
            response=result,
            error="LLM no disponible",
            sources=result.sources,
        )
        return result
    allowed, msg = check_rate_limit()
    if not allowed:
        sql_text, explanation = _generate_sql_heuristic(natural_query, df, logical_types, domain)
        result = AnalystResult(
            sql=sql_text,
            insight=explanation,
            recommendation="Esperá un momento antes de otra consulta LLM.",
            business_impact="Bajo",
            confidence="low",
            sources=["heuristic:nl_to_sql", "rate_limit"],
            used_llm=False,
            fallback_reason=msg,
            explanation=explanation,
        )
        _log_interaction(
            service.settings,
            operation="generate_sql_llm",
            query=natural_query,
            success=False,
            used_llm=False,
            response=result,
            error=msg,
            sources=result.sources,
        )
        return result
    return service.generate_sql_llm(natural_query, df, logical_types, domain)
