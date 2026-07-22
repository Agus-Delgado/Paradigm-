"""LEGACY flat experiment tracker (timestamped folders under ``ml/experiments/``).

Prefer the structured registry in ``ml.experiments`` (``runs/<run_id>/``).
Kept for forecast / older training scripts — not migrated yet.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib


@dataclass
class ExperimentTracker:
    """Tracks metadata and artifacts for one ML experiment run.

    The tracker creates a dedicated run directory under ``base_dir`` using an
    experiment id built from UTC timestamp and experiment name.
    """

    base_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    experiment_id: str | None = None
    run_dir: Path | None = None

    def __init__(self, base_dir: Path | None = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.base_dir = base_dir or (repo_root / "ml" / "experiments")
        self.metadata = {}
        self.experiment_id = None
        self.run_dir = None

    def start_experiment(
        self,
        name: str,
        model_type: str = "unspecified",
        hyperparameters: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> str:
        """Initialize metadata and create run directory.

        Returns:
            The generated experiment id.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = _slugify(name)
        self.experiment_id = f"{timestamp}_{safe_name}"
        self.run_dir = self.base_dir / self.experiment_id
        self.run_dir.mkdir(parents=True, exist_ok=False)

        self.metadata = {
            "experiment_id": self.experiment_id,
            "name": name,
            "timestamp": timestamp,
            "started_at_utc": _utc_iso_now(),
            "finished_at_utc": None,
            "status": "running",
            "model_type": model_type,
            "hyperparameters": hyperparameters or {},
            "metrics": {},
            "git_commit": _git_commit_hash(),
            "notes": notes or "",
            "artifacts": {},
        }
        self._write_metadata()
        return self.experiment_id

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        """Merge metric values into metadata and persist them."""
        self._ensure_started()
        current_metrics = self.metadata.setdefault("metrics", {})
        current_metrics.update(metrics)
        self._write_metadata()

    def log_model(self, model: Any, filename: str = "model.joblib") -> Path:
        """Persist a trained model artifact with joblib."""
        self._ensure_started()
        assert self.run_dir is not None

        model_path = self.run_dir / filename
        joblib.dump(model, model_path)

        artifacts = self.metadata.setdefault("artifacts", {})
        artifacts["model"] = str(model_path)
        self._write_metadata()
        return model_path

    def log_shap(self, shap_bundle: Any, filename: str = "shap_bundle.joblib") -> Path:
        """Persist SHAP bundle artifact with joblib."""
        self._ensure_started()
        assert self.run_dir is not None

        shap_path = self.run_dir / filename
        joblib.dump(shap_bundle, shap_path)

        artifacts = self.metadata.setdefault("artifacts", {})
        artifacts["shap_bundle"] = str(shap_path)
        self._write_metadata()
        return shap_path

    def finish_experiment(self, notes: str | None = None, status: str = "completed") -> Path:
        """Mark experiment as finished and persist final metadata."""
        self._ensure_started()

        self.metadata["status"] = status
        self.metadata["finished_at_utc"] = _utc_iso_now()
        if notes:
            existing_notes = self.metadata.get("notes", "")
            self.metadata["notes"] = f"{existing_notes}\n{notes}".strip()

        self._write_metadata()
        assert self.run_dir is not None
        return self.run_dir / "metadata.json"

    def _ensure_started(self) -> None:
        if self.run_dir is None or self.experiment_id is None:
            raise RuntimeError("Experiment not started. Call start_experiment() first.")

    def _write_metadata(self) -> None:
        self._ensure_started()
        assert self.run_dir is not None

        metadata_path = self.run_dir / "metadata.json"
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(self.metadata, handle, indent=2, ensure_ascii=False)


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(name: str) -> str:
    out = []
    for char in name.strip().lower().replace(" ", "_"):
        if char.isalnum() or char in {"_", "-"}:
            out.append(char)
    return "".join(out) or "experiment"


def _git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None
