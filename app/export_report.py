"""Generación de informes exportables (Markdown) para análisis y SQL."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.conversational.types import ContextualAnalysisResult, DatasetContext


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _df_to_md_table(df: pd.DataFrame, max_rows: int = 25) -> str:
    if df is None or df.empty:
        return "_Sin filas en el resultado._\n"
    sample = df.head(max_rows)
    headers = "| " + " | ".join(str(c) for c in sample.columns) + " |"
    sep = "| " + " | ".join("---" for _ in sample.columns) + " |"
    rows = []
    for _, row in sample.iterrows():
        cells = "| " + " | ".join(str(v).replace("|", "\\|")[:80] for v in row) + " |"
        rows.append(cells)
    out = "\n".join([headers, sep, *rows])
    if len(df) > max_rows:
        out += f"\n\n_Mostrando {max_rows} de {len(df):,} filas._"
    return out + "\n"


def build_analysis_report_md(
    result: ContextualAnalysisResult,
    ctx: DatasetContext,
    *,
    plan_objective: str | None = None,
) -> str:
    lines = [
        "# Paradigm — Informe de Análisis Guiado",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Generado | {_timestamp()} |",
        f"| Dataset | {ctx.source_label} |",
        f"| Dominio | `{ctx.domain}` |",
        f"| Filas | {len(ctx.df):,} |",
        f"| Columnas | {len(ctx.df.columns)} |",
        "",
    ]
    if plan_objective:
        lines.extend([f"**Objetivo de negocio:** {plan_objective}", ""])

    lines.extend([f"## {result.title}", "", result.summary, ""])

    if result.findings:
        lines.append("## Hallazgos clave\n")
        for item in result.findings:
            lines.append(f"- {item}")
        lines.append("")

    if result.recommendations:
        lines.append("## Recomendaciones (priorizadas por impacto)\n")
        for rec in result.recommendations:
            lines.append(f"- **[{rec.impact}]** {rec.text}")
        lines.append("")

    if result.data_used:
        lines.append("## Datos utilizados\n")
        lines.append(", ".join(f"«{c}»" for c in result.data_used))
        lines.append("")

    lines.extend(
        [
            "---",
            "_Generado por Paradigm Live Demo · datos sintéticos · sin LLM._",
        ]
    )
    return "\n".join(lines)


def build_sql_report_md(
    sql: str,
    result_df: pd.DataFrame | None,
    ctx: DatasetContext,
    *,
    nl_prompt: str | None = None,
    error: str | None = None,
) -> str:
    lines = [
        "# Paradigm — Informe SQL Explorer",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Generado | {_timestamp()} |",
        f"| Dataset | {ctx.source_label} |",
        f"| Tabla | `data` |",
        "",
    ]
    if nl_prompt:
        lines.extend([f"**Consulta en lenguaje natural:** {nl_prompt}", ""])

    lines.extend(["## SQL ejecutado", "", "```sql", sql.strip(), "```", ""])

    if error:
        lines.extend(["## Error", "", f"```\n{error}\n```", ""])
    elif result_df is not None:
        lines.extend(
            [
                f"## Resultados ({len(result_df):,} filas × {len(result_df.columns)} columnas)",
                "",
                _df_to_md_table(result_df),
            ]
        )

    lines.extend(
        [
            "---",
            "_Generado por Paradigm SQL Explorer · SQLite en memoria · solo lectura._",
        ]
    )
    return "\n".join(lines)


def build_ml_prediction_report_md(
    *,
    model_name: str,
    proba: float,
    level: str,
    recommendation: str,
    appointment_summary: str,
) -> str:
    lines = [
        "# Paradigm — Informe No-Show ML",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Generado | {_timestamp()} |",
        f"| Modelo | {model_name} |",
        f"| Probabilidad no-show | {proba * 100:.1f}% |",
        f"| Nivel de riesgo | {level} |",
        "",
        f"**Cita simulada:** {appointment_summary}",
        "",
        "## Recomendación operativa",
        "",
        recommendation,
        "",
        "---",
        "_Generado por Paradigm No-Show ML · datos sintéticos · priorización, no diagnóstico clínico._",
    ]
    return "\n".join(lines)
