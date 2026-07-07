"""Evaluation pipeline for conversational AI analyst responses."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.conversational.evaluation.metrics import (
    faithfulness_score,
    semantic_similarity_simple,
    sql_accuracy,
    sql_validity,
)
from ml.experiments.tracker import ExperimentTracker


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_eval_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "processed" / "evaluations"


@dataclass
class EvaluationSample:
    """Single unit for evaluation (one prompt-response pair)."""

    sample_id: str
    query: str
    response_text: str | None = None
    response_sql: str | None = None
    expected_text: str | None = None
    expected_sql: str | None = None
    sql_error: str | None = None
    evidence_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SampleEvaluation:
    """Computed metrics for one sample."""

    sample_id: str
    query: str
    metrics: dict[str, float]
    overall_score: float
    missing_metrics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunEvaluation:
    """Aggregated metrics for an evaluation run."""

    run_id: str
    created_at_utc: str
    n_samples: int
    average_metrics: dict[str, float]
    overall_score: float
    sample_inputs: list[EvaluationSample]
    sample_results: list[SampleEvaluation]
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationalEvaluator:
    """Evaluates conversational outputs with lightweight, extensible metrics."""

    def __init__(self, metric_weights: dict[str, float] | None = None) -> None:
        self.metric_weights = metric_weights or {
            "sql_validity": 0.30,
            "sql_accuracy": 0.30,
            "semantic_similarity": 0.25,
            "faithfulness": 0.15,
        }

    def evaluate_sample(self, sample: EvaluationSample) -> SampleEvaluation:
        expected_text = sample.expected_text or sample.query
        evidence_text = sample.evidence_text or sample.response_sql
        raw_metrics: dict[str, float | None] = {
            "sql_validity": sql_validity(sample.response_sql, sample.sql_error),
            "sql_accuracy": sql_accuracy(sample.response_sql, sample.expected_sql),
            "semantic_similarity": semantic_similarity_simple(sample.response_text, expected_text),
            "faithfulness": faithfulness_score(sample.response_text, evidence_text),
        }

        metrics = {k: float(v) for k, v in raw_metrics.items() if v is not None}
        missing = [k for k, v in raw_metrics.items() if v is None]
        overall = self._compute_weighted_score(metrics)

        return SampleEvaluation(
            sample_id=sample.sample_id,
            query=sample.query,
            metrics=metrics,
            overall_score=overall,
            missing_metrics=missing,
            metadata=sample.metadata,
        )

    def evaluate_run(
        self,
        samples: list[EvaluationSample],
        *,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunEvaluation:
        results = [self.evaluate_sample(sample) for sample in samples]
        averages = self._average_metrics(results)
        overall = self._compute_weighted_score(averages)

        return RunEvaluation(
            run_id=run_id or datetime.now(timezone.utc).strftime("eval_%Y%m%d_%H%M%S"),
            created_at_utc=_utc_now_iso(),
            n_samples=len(results),
            average_metrics=averages,
            overall_score=overall,
            sample_inputs=list(samples),
            sample_results=results,
            metadata=metadata or {},
        )

    def save_run(self, run: RunEvaluation, output_dir: Path | None = None) -> Path:
        """Persist run evaluation as JSON for later leaderboard loading."""
        folder = output_dir or _default_eval_dir()
        folder.mkdir(parents=True, exist_ok=True)
        out_path = folder / f"{run.run_id}.json"
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(run), handle, indent=2, ensure_ascii=False)
        return out_path

    def evaluate_and_save(
        self,
        samples: list[EvaluationSample],
        *,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        output_dir: Path | None = None,
    ) -> tuple[RunEvaluation, Path]:
        run = self.evaluate_run(samples, run_id=run_id, metadata=metadata)
        out_path = self.save_run(run, output_dir=output_dir)
        return run, out_path

    def save_run_with_tracker(
        self,
        run: RunEvaluation,
        *,
        tracker_base_dir: Path | None = None,
        name_prefix: str = "conversational_eval",
    ) -> Path:
        """Persist evaluation as an ExperimentTracker run artifact."""
        tracker = ExperimentTracker(base_dir=tracker_base_dir)
        tracker.start_experiment(
            name=f"{name_prefix}_{run.run_id}",
            model_type="conversational_evaluation",
            hyperparameters={
                "n_samples": run.n_samples,
                "metric_weights": self.metric_weights,
            },
            notes="Automated evaluation run for AI Conversational Analyst.",
        )

        tracker.log_metrics(
            {
                "overall_score": run.overall_score,
                "n_samples": run.n_samples,
                **run.average_metrics,
            }
        )
        assert tracker.run_dir is not None
        out_path = tracker.run_dir / "evaluation.json"
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(run), handle, indent=2, ensure_ascii=False)
        tracker.finish_experiment(status="completed")
        return out_path

    @staticmethod
    def samples_from_chat_history(
        chat_history: list[dict[str, Any]],
        *,
        run_label: str = "chat",
        expected_text_by_index: dict[int, str] | None = None,
        expected_sql_by_index: dict[int, str] | None = None,
    ) -> list[EvaluationSample]:
        """Build evaluation samples from AI Analyst in-session chat history."""
        text_refs = expected_text_by_index or {}
        sql_refs = expected_sql_by_index or {}
        samples: list[EvaluationSample] = []

        for idx, turn in enumerate(chat_history):
            payload = turn.get("payload", {}) or {}
            query = str(turn.get("query", ""))
            samples.append(
                EvaluationSample(
                    sample_id=f"{run_label}_turn_{idx + 1}",
                    query=query,
                    response_text=payload.get("insight"),
                    response_sql=payload.get("sql"),
                    expected_text=text_refs.get(idx),
                    expected_sql=sql_refs.get(idx),
                    evidence_text=payload.get("sql") or query,
                    metadata={
                        "turn_index": idx,
                        "used_llm": payload.get("used_llm"),
                        "confidence": payload.get("confidence"),
                    },
                )
            )
        return samples

    def _average_metrics(self, sample_results: list[SampleEvaluation]) -> dict[str, float]:
        if not sample_results:
            return {}

        bucket: dict[str, list[float]] = {}
        for result in sample_results:
            for metric_name, value in result.metrics.items():
                bucket.setdefault(metric_name, []).append(float(value))

        return {
            metric_name: (sum(values) / len(values))
            for metric_name, values in bucket.items()
            if values
        }

    def _compute_weighted_score(self, metrics: dict[str, float]) -> float:
        if not metrics:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for metric_name, value in metrics.items():
            weight = float(self.metric_weights.get(metric_name, 0.0))
            if weight <= 0.0:
                continue
            weighted_sum += value * weight
            total_weight += weight

        if total_weight <= 0.0:
            return sum(metrics.values()) / len(metrics)
        return weighted_sum / total_weight
