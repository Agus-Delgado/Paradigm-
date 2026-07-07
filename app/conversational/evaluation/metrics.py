"""Core metrics for conversational AI analyst evaluation."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_STOPWORDS = {
    "a",
    "al",
    "and",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "la",
    "las",
    "los",
    "of",
    "or",
    "para",
    "por",
    "que",
    "the",
    "un",
    "una",
    "y",
}

_DANGEROUS_SQL_PATTERNS = (
    r"\bdelete\b",
    r"\bdrop\b",
    r"\binsert\b",
    r"\balter\b",
    r"\bupdate\b",
    r"\btruncate\b",
    r"\bcreate\b",
)


def _bounded_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return {tok for tok in tokens if len(tok) > 1 and tok not in _STOPWORDS}


def normalize_sql(sql: str | None) -> str:
    """Normalize SQL for stable lexical comparisons."""
    if not sql:
        return ""
    compact = re.sub(r"\s+", " ", sql.strip().lower())
    return compact.rstrip(";")


def sql_is_read_only(sql: str | None) -> bool:
    """Returns True when SQL appears to be a read-only query."""
    text = normalize_sql(sql)
    if not text:
        return False
    if not (text.startswith("select") or text.startswith("with")):
        return False
    return not any(re.search(pattern, text) for pattern in _DANGEROUS_SQL_PATTERNS)


def sql_validity(sql: str | None, sql_error: str | None = None) -> float:
    """Heuristic validity: non-empty, read-only, and no execution error."""
    if sql_error:
        return 0.0
    return 1.0 if sql_is_read_only(sql) else 0.0


def sql_accuracy(predicted_sql: str | None, expected_sql: str | None) -> float | None:
    """Exact normalized SQL match when a reference query is available."""
    expected_norm = normalize_sql(expected_sql)
    if not expected_norm:
        return None
    return 1.0 if normalize_sql(predicted_sql) == expected_norm else 0.0


def semantic_similarity_simple(predicted_text: str | None, expected_text: str | None) -> float | None:
    """Simple semantic proxy using lexical overlap + sequence similarity."""
    expected = (expected_text or "").strip()
    if not expected:
        return None
    predicted = (predicted_text or "").strip()
    if not predicted:
        return 0.0

    ratio = SequenceMatcher(a=predicted.lower(), b=expected.lower()).ratio()
    tok_a = _tokenize(predicted)
    tok_b = _tokenize(expected)
    jaccard = 0.0 if not tok_a or not tok_b else len(tok_a & tok_b) / len(tok_a | tok_b)
    return _bounded_score((ratio * 0.5) + (jaccard * 0.5))


def faithfulness_score(answer_text: str | None, evidence_text: str | None) -> float | None:
    """Faithfulness proxy via token overlap between answer and evidence."""
    evidence = (evidence_text or "").strip()
    if not evidence:
        return None
    answer = (answer_text or "").strip()
    if not answer:
        return 0.0

    evidence_tokens = _tokenize(evidence)
    if not evidence_tokens:
        return None

    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 0.0

    coverage = len(answer_tokens & evidence_tokens) / len(answer_tokens)
    return _bounded_score(coverage)
