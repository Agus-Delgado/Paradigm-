"""Run conversational evaluation on a gold dataset and generate a JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.conversational.evaluation.evaluator import ConversationalEvaluator, EvaluationSample


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _load_gold(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Gold file must be a JSON array of samples.")
    return [item for item in payload if isinstance(item, dict)]


def _to_sample(item: dict[str, Any], idx: int) -> EvaluationSample:
    sample_id = str(item.get("id") or f"gold_{idx + 1}")
    return EvaluationSample(
        sample_id=sample_id,
        query=str(item.get("pregunta", "")),
        response_text=item.get("respuesta_generada"),
        response_sql=item.get("sql_generado"),
        expected_text=item.get("respuesta_esperada"),
        expected_sql=item.get("sql_esperado"),
        evidence_text=item.get("contexto"),
        metadata={"source": "gold", "gold_id": sample_id},
    )


def _evaluate_expected(
    sample_results: list[dict[str, Any]],
    gold_items: list[dict[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    passed = 0
    total = 0

    for idx, result in enumerate(sample_results):
        expected = (gold_items[idx].get("expected_metrics") or {}) if idx < len(gold_items) else {}
        if not isinstance(expected, dict):
            expected = {}

        actual_metrics = result.get("metrics", {}) or {}
        for metric_name, expected_value in expected.items():
            if not isinstance(expected_value, (int, float)):
                continue
            total += 1
            actual_value = actual_metrics.get(metric_name)
            if not isinstance(actual_value, (int, float)):
                checks.append(
                    {
                        "sample_id": result.get("sample_id"),
                        "metric": metric_name,
                        "expected": float(expected_value),
                        "actual": None,
                        "delta": None,
                        "pass": False,
                        "reason": "missing_metric",
                    }
                )
                continue

            delta = abs(float(actual_value) - float(expected_value))
            ok = delta <= tolerance
            if ok:
                passed += 1
            checks.append(
                {
                    "sample_id": result.get("sample_id"),
                    "metric": metric_name,
                    "expected": round(float(expected_value), 4),
                    "actual": round(float(actual_value), 4),
                    "delta": round(delta, 4),
                    "pass": ok,
                }
            )

    return {
        "checks": checks,
        "passed": passed,
        "total": total,
        "pass_rate": (passed / total) if total else 0.0,
        "tolerance": tolerance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run conversational evaluation on gold dataset.")
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "eval_gold" / "conversational_eval_gold.json",
        help="Path to gold JSON dataset.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "reports" / "evaluation_gold_report.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.20,
        help="Tolerance for expected metric checks.",
    )
    args = parser.parse_args()

    gold_items = _load_gold(args.gold)
    samples = [_to_sample(item, idx) for idx, item in enumerate(gold_items)]

    evaluator = ConversationalEvaluator()
    run = evaluator.evaluate_run(
        samples,
        run_id=f"gold_eval_{_utc_stamp()}",
        metadata={"gold_path": str(args.gold), "n_gold": len(gold_items)},
    )

    expected_check = _evaluate_expected(
        sample_results=[{"sample_id": s.sample_id, "metrics": s.metrics} for s in run.sample_results],
        gold_items=gold_items,
        tolerance=args.tolerance,
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "gold_path": str(args.gold),
        "run_id": run.run_id,
        "n_samples": run.n_samples,
        "overall_score": round(float(run.overall_score), 4),
        "average_metrics": {k: round(float(v), 4) for k, v in run.average_metrics.items()},
        "expected_checks": expected_check,
        "samples": [
            {
                "sample_id": s.sample_id,
                "query": s.query,
                "metrics": {k: round(float(v), 4) for k, v in s.metrics.items()},
                "overall_score": round(float(s.overall_score), 4),
                "missing_metrics": s.missing_metrics,
            }
            for s in run.sample_results
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Gold samples: {len(gold_items)}")
    print(f"Run ID: {run.run_id}")
    print(f"Overall score: {run.overall_score:.4f}")
    print(
        "Expected checks: "
        f"{expected_check['passed']}/{expected_check['total']} "
        f"(pass_rate={expected_check['pass_rate']:.2%}, tolerance={args.tolerance:.2f})"
    )
    print(f"Report written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
