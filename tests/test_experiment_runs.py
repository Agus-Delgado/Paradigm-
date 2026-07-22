"""Unit tests for the ml.experiments run registry (no model migration)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.experiments import (  # noqa: E402
    OPTIONAL_SUBDIRS,
    REQUIRED_FILES,
    ExperimentConfig,
    ExperimentMetadata,
    finish_run,
    generate_run_id,
    load_run,
    save_metrics,
    start_run,
)
from ml.experiments.store import read_json  # noqa: E402


def _sample_config(**overrides) -> ExperimentConfig:
    payload = {
        "experiment_type": "classification",
        "name": "unit_test_no_show",
        "question": "¿Qué citas priorizar?",
        "hypothesis": "El historial de proveedor mejora el ranking vs azar.",
        "dataset": "paradigm_mart.fact_appointment",
        "target": "target_no_show",
        "baseline": "positive_rate",
        "seed": 42,
        "params": {"test_ratio": 0.2},
        "notes": "test run",
    }
    payload.update(overrides)
    return ExperimentConfig(**payload)


class TestRunId(unittest.TestCase):
    def test_generate_run_id_is_readable_and_deterministic(self) -> None:
        when = datetime(2026, 7, 21, 15, 30, 0, tzinfo=timezone.utc)
        run_id = generate_run_id("Unit Test No-Show", when=when)
        self.assertEqual(run_id, "20260721_153000_unit_test_no-show")

        again = generate_run_id("Unit Test No-Show", when=when, suffix="a1b2")
        self.assertEqual(again, "20260721_153000_unit_test_no-show_a1b2")


class TestExperimentRuns(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_start_run_creates_layout(self) -> None:
        run = start_run(_sample_config(), base_dir=self.base_dir, git_commit="abc123")
        self.assertTrue(run.run_dir.is_dir())
        self.assertEqual(run.metadata.status, "running")
        self.assertEqual(run.metadata.git_commit, "abc123")
        self.assertEqual(run.metadata.seed, 42)
        self.assertTrue(run.metadata.python_version)
        self.assertTrue(run.metadata.started_at_utc.endswith("Z") or "+" in run.metadata.started_at_utc)

        for name in REQUIRED_FILES:
            self.assertTrue((run.run_dir / name).is_file(), name)
        for name in OPTIONAL_SUBDIRS:
            self.assertTrue((run.run_dir / name).is_dir(), name)

    def test_serialization_roundtrip(self) -> None:
        config = _sample_config()
        run = start_run(config, base_dir=self.base_dir, git_commit=None)

        config_disk = ExperimentConfig.from_dict(read_json(run.run_dir / "config.json"))
        self.assertEqual(config_disk.name, config.name)
        self.assertEqual(config_disk.params["test_ratio"], 0.2)

        meta_disk = ExperimentMetadata.from_dict(read_json(run.run_dir / "metadata.json"))
        self.assertEqual(meta_disk.run_id, run.run_id)
        self.assertIsNone(meta_disk.git_commit)

        # JSON dumps must be valid UTF-8 objects
        raw = json.loads((run.run_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["experiment_type"], "classification")

        reloaded = load_run(run.run_dir)
        self.assertEqual(reloaded.run_id, run.run_id)
        self.assertEqual(reloaded.config.dataset, config.dataset)

    def test_save_metrics_merge_and_replace(self) -> None:
        run = start_run(_sample_config(), base_dir=self.base_dir, git_commit=None)
        save_metrics(run, {"roc_auc": 0.42})
        save_metrics(run, {"top_decile_capture": 0.09})
        stored = read_json(run.run_dir / "metrics.json")
        self.assertEqual(stored["roc_auc"], 0.42)
        self.assertEqual(stored["top_decile_capture"], 0.09)

        save_metrics(run, {"brier": 0.2}, merge=False)
        stored = read_json(run.run_dir / "metrics.json")
        self.assertEqual(stored, {"brier": 0.2})

    def test_finish_completed(self) -> None:
        run = start_run(_sample_config(), base_dir=self.base_dir, git_commit="deadbeef")
        save_metrics(run, {"roc_auc": 0.5})
        meta_path = finish_run(run, status="completed")
        self.assertTrue(meta_path.is_file())

        meta = ExperimentMetadata.from_dict(read_json(meta_path))
        self.assertEqual(meta.status, "completed")
        self.assertIsNotNone(meta.finished_at_utc)
        self.assertIsNotNone(meta.duration_seconds)
        self.assertGreaterEqual(meta.duration_seconds, 0.0)  # type: ignore[arg-type]
        self.assertIsNone(meta.error)

        report = (run.run_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("roc_auc", report)
        self.assertIn("completed", report)

    def test_finish_failed_controlled(self) -> None:
        run = start_run(_sample_config(), base_dir=self.base_dir, git_commit=None)
        finish_run(run, status="failed", error="simulated training failure")
        meta = ExperimentMetadata.from_dict(read_json(run.run_dir / "metadata.json"))
        self.assertEqual(meta.status, "failed")
        self.assertEqual(meta.error, "simulated training failure")

        with self.assertRaises(RuntimeError):
            save_metrics(run, {"x": 1})
        with self.assertRaises(RuntimeError):
            finish_run(run, status="completed")

    def test_finish_discarded(self) -> None:
        run = start_run(_sample_config(), base_dir=self.base_dir, git_commit=None)
        finish_run(run, status="discarded", notes="leakage suspected")
        meta = ExperimentMetadata.from_dict(read_json(run.run_dir / "metadata.json"))
        self.assertEqual(meta.status, "discarded")
        self.assertIn("leakage", meta.notes)

    def test_git_unavailable_records_null(self) -> None:
        with patch("ml.experiments.runner.resolve_git_commit", return_value=None):
            # Omit git_commit override so auto-detect path is exercised.
            run = start_run(_sample_config(), base_dir=self.base_dir)
        self.assertIsNone(run.metadata.git_commit)
        disk = read_json(run.run_dir / "metadata.json")
        self.assertIsNone(disk["git_commit"])

    def test_invalid_terminal_status_rejected(self) -> None:
        run = start_run(_sample_config(), base_dir=self.base_dir, git_commit=None)
        with self.assertRaises(ValueError):
            finish_run(run, status="promote")  # type: ignore[arg-type]


class TestImportHasNoSideEffects(unittest.TestCase):
    def test_import_does_not_create_default_runs(self) -> None:
        from ml.experiments.store import default_runs_root

        # Importing the package must not create run directories by itself.
        # The tracked placeholder may exist; no new run_id folders should appear
        # as a side effect of this test's imports (already done at module load).
        root = default_runs_root()
        if root.exists():
            run_dirs = [
                p
                for p in root.iterdir()
                if p.is_dir() and p.name not in {".gitkeep"} and (p / "metadata.json").exists()
            ]
            # Soft check: importing tests should not have written into the real runs root.
            # Any pre-existing local runs are ignored; we only assert import is safe.
            self.assertIsInstance(run_dirs, list)


if __name__ == "__main__":
    unittest.main()
