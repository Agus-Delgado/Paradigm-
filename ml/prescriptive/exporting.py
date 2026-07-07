"""Export helpers for prescriptive recommendations and executive reporting."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json
import zipfile

import pandas as pd


def export_recommendations_to_csv(
    recommendations: pd.DataFrame,
    out_dir: Path,
    *,
    prefix: str = "prescriptive_recommendations",
) -> Path:
    """Persist recommendations to a timestamped CSV file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{prefix}_{timestamp}.csv"
    recommendations.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def generate_executive_report_md(
    *,
    model_name: str,
    summary: dict[str, Any],
    recommendations: pd.DataFrame,
    before_after: pd.DataFrame,
    intervention_breakdown: pd.DataFrame,
    simulation_settings: dict[str, Any] | None = None,
    max_rows: int = 25,
) -> str:
    """Build a markdown executive report for prescriptive what-if simulation."""
    settings = simulation_settings or {}
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    top_reco = recommendations.sort_values("priority_score", ascending=False).head(max_rows)
    key_metrics = {
        "Slots recuperados (media)": _fmt_float(summary.get("slots_recovered_mean"), 2),
        "Slots recuperados p05": _fmt_float(summary.get("slots_recovered_p05"), 2),
        "Slots recuperados p95": _fmt_float(summary.get("slots_recovered_p95"), 2),
        "Revenue bruto (media ARS)": _fmt_currency(summary.get("revenue_impact_mean_ars")),
        "Costo intervención (media ARS)": _fmt_currency(summary.get("cost_mean_ars")),
        "Revenue neto (media ARS)": _fmt_currency(summary.get("net_impact_mean_ars")),
    }

    lines: list[str] = [
        "# Paradigm — Prescriptive AI Executive Report",
        "",
        f"- Fecha de generación: {now_str}",
        f"- Modelo no-show: {model_name}",
        f"- Iteraciones Monte Carlo: {settings.get('iterations', 'n/a')}",
        f"- Fill rate overbooking: {settings.get('overbooking_fill_rate', 'n/a')}",
        f"- Uso de forecast: {settings.get('include_forecast', 'n/a')}",
        "",
        "## Summary",
        "",
    ]

    for key, value in key_metrics.items():
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## Before vs After",
            "",
            _markdown_table(before_after, max_rows=10),
            "",
            "## Tabla Priorizada (Top)",
            "",
            _markdown_table(
                top_reco,
                columns=[
                    "display_id",
                    "appointment_date",
                    "predicted_proba",
                    "recommended_intervention",
                    "expected_slots_recovered",
                    "expected_revenue_ars",
                    "expected_cost_ars",
                    "expected_net_ars",
                    "priority_score",
                ],
                max_rows=max_rows,
            ),
            "",
            "## Mix de Intervenciones",
            "",
            _markdown_table(intervention_breakdown, max_rows=20),
            "",
            "_Reporte generado desde Paradigm No-Show ML · capa prescriptiva (simulación what-if)._",
        ]
    )
    return "\n".join(lines)


def export_prescriptive_package_zip(
    *,
    out_dir: Path,
    recommendations: pd.DataFrame,
    executive_report_md: str,
    summary: dict[str, Any],
    before_after: pd.DataFrame | None = None,
    prefix: str = "prescriptive_package",
) -> Path:
    """Create a timestamped ZIP package with prescriptive simulation artifacts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = out_dir / f"{prefix}_{timestamp}.zip"

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("recommendations.csv", recommendations.to_csv(index=False, encoding="utf-8"))
        zf.writestr("executive_report.md", executive_report_md)
        zf.writestr("summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
        if before_after is not None and not before_after.empty:
            zf.writestr("before_after.csv", before_after.to_csv(index=False, encoding="utf-8"))

    return zip_path


def _markdown_table(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    *,
    max_rows: int,
) -> str:
    if frame.empty:
        return "Sin datos."

    table = frame.copy()
    if columns:
        existing = [col for col in columns if col in table.columns]
        if existing:
            table = table[existing]

    head = table.head(max(max_rows, 1)).copy()
    headers = list(head.columns)
    sep = ["---"] * len(headers)
    rows = [headers, sep]

    for _, row in head.iterrows():
        values = [_fmt_cell(row[col]) for col in headers]
        rows.append(values)

    return "\n".join(["| " + " | ".join(r) + " |" for r in rows])


def _fmt_cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.4f}" if abs(value) < 1000 else f"{value:,.2f}"
    return str(value)


def _fmt_float(value: Any, digits: int) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "n/a"


def _fmt_currency(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return "n/a"
