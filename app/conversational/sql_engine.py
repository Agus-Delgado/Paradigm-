"""Motor SQLite en memoria para SQL Explorer (stdlib, sin dependencias extra)."""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from typing import Iterator

import pandas as pd

TABLE_NAME = "data"

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def register_dataframe(conn: sqlite3.Connection, df: pd.DataFrame, table: str = TABLE_NAME) -> None:
    """Registra el DataFrame como tabla SQLite."""
    df.to_sql(table, conn, index=False, if_exists="replace")


@contextmanager
def memory_connection(df: pd.DataFrame, table: str = TABLE_NAME) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    try:
        register_dataframe(conn, df, table)
        yield conn
    finally:
        conn.close()


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql.strip()


def is_safe_sql(sql: str) -> bool:
    """Solo permite consultas de lectura (SELECT / WITH)."""
    cleaned = _strip_sql_comments(sql)
    if not cleaned:
        return False
    if _FORBIDDEN.search(cleaned):
        return False
    upper = cleaned.upper().lstrip()
    return upper.startswith("SELECT") or upper.startswith("WITH")


def execute_sql(conn: sqlite3.Connection, sql: str) -> tuple[pd.DataFrame | None, str | None]:
    if not is_safe_sql(sql):
        return None, "Solo se permiten consultas SELECT o WITH (lectura)."
    try:
        result = pd.read_sql_query(sql, conn)
        return result, None
    except Exception as exc:
        return None, str(exc)


def execute_sql_on_dataframe(df: pd.DataFrame, sql: str) -> tuple[pd.DataFrame | None, str | None]:
    """Ejecuta SQL sobre una copia temporal en memoria del DataFrame."""
    with memory_connection(df) as conn:
        return execute_sql(conn, sql)


def cache_key(dataset_key: str) -> str:
    return f"sql_engine_ready_{dataset_key}"


def invalidate_cache(dataset_key: str | None = None) -> None:
    """Limpia flags de caché SQL en session_state (solo contexto Streamlit)."""
    import streamlit as st

    for k in list(st.session_state.keys()):
        if not k.startswith("sql_"):
            continue
        if dataset_key is None or dataset_key in k:
            del st.session_state[k]


def ensure_engine_ready(dataset_key: str, df: pd.DataFrame) -> None:
    """Marca el engine como listo para este dataset (solo contexto Streamlit)."""
    import streamlit as st

    st.session_state[cache_key(dataset_key)] = {
        "rows": len(df),
        "cols": len(df.columns),
        "table": TABLE_NAME,
    }
