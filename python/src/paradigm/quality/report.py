"""Genera reporte Markdown de calidad."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from paradigm.quality.results import CheckResult, Severity


def render_markdown(results: list[CheckResult], db_path: str) -> str:
    lines = [
        "# Reporte de calidad de datos — Paradigm v2",
        "",
        f"- **Generado (UTC):** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
        f"- **Base:** `{db_path}`",
        "",
        "| Severidad | ID | Nombre | Detalle | Métrica |",
        "|-----------|-----|--------|---------|---------|",
    ]
    for r in results:
        mv = "" if r.metric_value is None else str(r.metric_value)
        lines.append(
            f"| {r.severity.value} | {r.check_id} | {r.name} | {r.detail} | {mv} |"
        )
    lines.extend(
        [
            "",
            "## Leyenda",
            "",
            "- **ok:** criterio cumplido.",
            "- **warn:** regla de negocio o brecha esperada en datos sintéticos (revisar texto).",
            "- **fail:** incumplimiento que debe corregirse antes de consumo BI.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(results: list[CheckResult], db_path: Path, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = render_markdown(results, str(db_path.as_posix()))
    out_path.write_text(text, encoding="utf-8")
