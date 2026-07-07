"""Leaderboard helpers for conversational evaluation runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


def _default_eval_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "processed" / "evaluations"


@dataclass
class LeaderboardRow:
    run_id: str
    created_at_utc: str
    n_samples: int
    overall_score: float
    average_metrics: dict[str, float]
    metadata: dict[str, Any]
    file_path: str


def load_evaluation_runs(eval_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load raw run JSON payloads from evaluation directory."""
    folder = eval_dir or _default_eval_dir()
    if not folder.exists():
        return []

    runs: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload["_file_path"] = str(path)
        runs.append(payload)
    return runs


def build_leaderboard(eval_dir: Path | None = None) -> list[LeaderboardRow]:
    """Create sorted leaderboard rows from saved run evaluations."""
    rows: list[LeaderboardRow] = []
    for run in load_evaluation_runs(eval_dir=eval_dir):
        rows.append(
            LeaderboardRow(
                run_id=str(run.get("run_id", "unknown")),
                created_at_utc=str(run.get("created_at_utc", "")),
                n_samples=int(run.get("n_samples", 0) or 0),
                overall_score=float(run.get("overall_score", 0.0) or 0.0),
                average_metrics={
                    k: float(v)
                    for k, v in (run.get("average_metrics", {}) or {}).items()
                    if isinstance(v, (int, float))
                },
                metadata=dict(run.get("metadata", {}) or {}),
                file_path=str(run.get("_file_path", "")),
            )
        )

    rows.sort(key=lambda row: (row.overall_score, row.created_at_utc), reverse=True)
    return rows


def leaderboard_dataframe(eval_dir: Path | None = None) -> pd.DataFrame:
    """Return a leaderboard dataframe for Streamlit rendering."""
    rows = build_leaderboard(eval_dir=eval_dir)
    if not rows:
        return pd.DataFrame(
            columns=[
                "rank",
                "run_id",
                "created_at_utc",
                "n_samples",
                "overall_score",
            ]
        )

    records: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        record: dict[str, Any] = {
            "rank": idx,
            "run_id": row.run_id,
            "created_at_utc": row.created_at_utc,
            "n_samples": row.n_samples,
            "overall_score": round(row.overall_score, 4),
            "file_path": row.file_path,
        }
        for metric_name, metric_value in row.average_metrics.items():
            record[metric_name] = round(float(metric_value), 4)
        records.append(record)

    return pd.DataFrame.from_records(records)


def average_of_averages(eval_dir: Path | None = None) -> dict[str, float]:
    """Compute macro-average metrics across all runs in leaderboard."""
    rows = build_leaderboard(eval_dir=eval_dir)
    if not rows:
        return {}

    bucket: dict[str, list[float]] = {}
    for row in rows:
        bucket.setdefault("overall_score", []).append(float(row.overall_score))
        for metric_name, value in row.average_metrics.items():
            bucket.setdefault(metric_name, []).append(float(value))

    return {
        metric_name: (sum(values) / len(values))
        for metric_name, values in bucket.items()
        if values
    }
