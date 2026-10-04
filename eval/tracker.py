"""
eval/tracker.py
---------------
Standardized MLflow experiment tracking for ASTCV.

Enforces project-wide naming conventions and auto-logs environment context
(git commit, branch, DVC dataset versions, Python version, platform) with
every run — so results stay reproducible and auditable.

Naming conventions (enforced):
  Experiment : phase{N}_{description}   e.g. phase1_sync_baseline
  Run        : {device}_{dataset}_{date} e.g. pixel7_ff++_20261005

Owner: M3 (Aswin K N)

Usage:
    from eval.tracker import ASTCVRun, setup_experiment

    # One-time setup (call once per experiment, idempotent)
    setup_experiment("phase1_sync_baseline")

    # Log a run
    with ASTCVRun(
        experiment="phase1_sync_baseline",
        run_name="pixel7_ff++_20261005",
        dataset="ff++",
        device="pixel7",
        tags={"phase": "1", "owner": "M3"},
    ) as run:
        run.log_params({"threshold": 0.5, "batch_size": 32})
        run.log_eval_metrics(far=0.03, frr=0.015, latency_ms=120.0)
        run.log_dataset_version("ff++", version="v1.0", split="test", n_samples=1000)
        run.log_artifact_path("path/to/roc_curve.png")
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import mlflow

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# SQLite backend — required by MLflow 3.x (file-store is deprecated).
# DB lives at experiments/mlflow.db (DVC-tracked, not in git).
# Artifacts live at experiments/mlartifacts/ (DVC-tracked, not in git).
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"
TRACKING_URI = f"sqlite:///{_EXPERIMENTS_DIR / 'mlflow.db'}"
ARTIFACT_LOCATION = str(_EXPERIMENTS_DIR / "mlartifacts")

# Naming convention regex patterns
EXPERIMENT_NAME_RE = re.compile(r"^phase\d+_.+$")
RUN_NAME_RE = re.compile(r"^[a-zA-Z0-9_+\-\.]+_[a-zA-Z0-9_+\-\.]+_\d{8}$")


# ---------------------------------------------------------------------------
# Naming convention helpers
# ---------------------------------------------------------------------------

def validate_experiment_name(name: str) -> None:
    """Raise ValueError if experiment name does not follow phase{N}_{description}."""
    if not EXPERIMENT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid experiment name: '{name}'. "
            f"Must follow 'phase{{N}}_{{description}}', e.g. 'phase1_sync_baseline'."
        )


def validate_run_name(name: str) -> None:
    """Raise ValueError if run name does not follow {device}_{dataset}_{YYYYMMDD}."""
    if not RUN_NAME_RE.match(name):
        raise ValueError(
            f"Invalid run name: '{name}'. "
            f"Must follow '{{device}}_{{dataset}}_{{YYYYMMDD}}', "
            f"e.g. 'pixel7_ff++_20261005'."
        )


def today_str() -> str:
    """Return today's date as YYYYMMDD string (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def make_run_name(device: str, dataset: str, date: Optional[str] = None) -> str:
    """
    Construct a compliant run name.

    Args:
        device:  Device identifier, e.g. 'pixel7', 'dellxps15'
        dataset: Dataset identifier, e.g. 'ff++', 'custom_v1'
        date:    Optional YYYYMMDD string. Defaults to today (UTC).

    Returns:
        Formatted run name string.
    """
    return f"{device}_{dataset}_{date or today_str()}"


# ---------------------------------------------------------------------------
# Experiment setup
# ---------------------------------------------------------------------------

def setup_experiment(name: str) -> str:
    """
    Create or retrieve an MLflow experiment by name.

    Enforces naming convention and configures the local tracking URI.

    Args:
        name: Experiment name following phase{N}_{description} convention.

    Returns:
        MLflow experiment ID.
    """
    validate_experiment_name(name)
    mlflow.set_tracking_uri(TRACKING_URI)
    experiment = mlflow.get_experiment_by_name(name)
    if experiment is None:
        exp_id = mlflow.create_experiment(name, artifact_location=ARTIFACT_LOCATION)
        print(f"[tracker] Created experiment '{name}' (id={exp_id})")
    else:
        exp_id = experiment.experiment_id
        print(f"[tracker] Using existing experiment '{name}' (id={exp_id})")
    return exp_id


# ---------------------------------------------------------------------------
# Environment context helpers
# ---------------------------------------------------------------------------

def _get_git_info() -> Dict[str, str]:
    """Collect git commit hash and branch name. Returns empty dict on failure."""
    info: Dict[str, str] = {}
    try:
        info["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        info["git_branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        # Check if working tree is dirty
        dirty = subprocess.call(
            ["git", "diff", "--quiet"],
            stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
        )
        info["git_dirty"] = str(bool(dirty))
    except (subprocess.CalledProcessError, FileNotFoundError):
        info["git_commit"] = "unavailable"
    return info


def _get_system_info() -> Dict[str, str]:
    """Collect Python version and platform details."""
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": platform.node(),
    }


def _get_dvc_versions(data_paths: Optional[list[str]] = None) -> Dict[str, str]:
    """
    Attempt to read DVC-tracked file hashes for given paths.
    These act as dataset version identifiers.

    Args:
        data_paths: List of DVC-tracked paths to log versions for.

    Returns:
        Dict mapping path → DVC md5 hash (or 'unavailable').
    """
    if not data_paths:
        return {}
    versions: Dict[str, str] = {}
    for path in data_paths:
        dvc_file = Path(path + ".dvc")
        if dvc_file.exists():
            try:
                import yaml  # PyYAML ships with DVC
                with dvc_file.open() as f:
                    meta = yaml.safe_load(f)
                md5 = meta.get("outs", [{}])[0].get("md5", "no_md5")
                versions[f"dvc_{Path(path).name}"] = md5
            except Exception:
                versions[f"dvc_{Path(path).name}"] = "parse_error"
        else:
            versions[f"dvc_{Path(path).name}"] = "no_dvc_file"
    return versions


# ---------------------------------------------------------------------------
# ASTCVRun — the main tracking context manager
# ---------------------------------------------------------------------------

class ASTCVRun:
    """
    Context manager for a single ASTCV MLflow run.

    Automatically logs environment context (git, system, DVC) on enter.
    Provides helper methods for logging standard ASTCV metrics.

    Example:
        with ASTCVRun(
            experiment="phase1_sync_baseline",
            run_name="pixel7_ff++_20261005",
            dataset="ff++",
            device="pixel7",
        ) as run:
            run.log_params({"threshold": 0.5})
            run.log_eval_metrics(far=0.03, frr=0.015, latency_ms=122.0)
    """

    def __init__(
        self,
        experiment: str,
        run_name: str,
        dataset: str,
        device: str,
        tags: Optional[Dict[str, str]] = None,
        dvc_data_paths: Optional[list[str]] = None,
    ):
        """
        Args:
            experiment:      Must follow phase{N}_{description}.
            run_name:        Must follow {device}_{dataset}_{YYYYMMDD}.
            dataset:         Dataset identifier string logged as a tag.
            device:          Device identifier string logged as a tag.
            tags:            Additional key-value tags to attach to the run.
            dvc_data_paths:  DVC-tracked data paths whose hashes will be logged.
        """
        validate_experiment_name(experiment)
        validate_run_name(run_name)

        self.experiment = experiment
        self.run_name = run_name
        self.dataset = dataset
        self.device = device
        self.tags = tags or {}
        self.dvc_data_paths = dvc_data_paths or []
        self._active_run: Optional[mlflow.ActiveRun] = None

    def __enter__(self) -> "ASTCVRun":
        mlflow.set_tracking_uri(TRACKING_URI)
        mlflow.set_experiment(self.experiment)

        combined_tags = {
            "dataset": self.dataset,
            "device": self.device,
            **self.tags,
        }

        self._active_run = mlflow.start_run(run_name=self.run_name, tags=combined_tags)

        # Auto-log environment context
        git_info = _get_git_info()
        sys_info = _get_system_info()
        dvc_info = _get_dvc_versions(self.dvc_data_paths)

        env_params = {**git_info, **sys_info, **dvc_info}
        if env_params:
            mlflow.log_params(env_params)

        print(
            f"[tracker] Run started: experiment='{self.experiment}' "
            f"run='{self.run_name}' id={self._active_run.info.run_id[:8]}..."
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            mlflow.set_tag("run_status", "FAILED")
            mlflow.set_tag("error", str(exc_val))
        else:
            mlflow.set_tag("run_status", "COMPLETED")
        mlflow.end_run()
        status = "FAILED" if exc_type else "COMPLETED"
        print(f"[tracker] Run ended: {self.run_name} -> {status}")
        return False  # do not suppress exceptions

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log arbitrary hyperparameters / config values."""
        mlflow.log_params(params)

    def log_eval_metrics(
        self,
        far: Optional[float] = None,
        frr: Optional[float] = None,
        latency_ms: Optional[float] = None,
        step: Optional[int] = None,
        extra: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Log the three primary ASTCV evaluation metrics with standard names.

        Args:
            far:        False Acceptance Rate (0.0–1.0)
            frr:        False Rejection Rate (0.0–1.0)
            latency_ms: End-to-end decision latency in milliseconds
            step:       Optional MLflow step index (for multi-step logging)
            extra:      Additional metric key-value pairs
        """
        metrics: Dict[str, float] = {}
        if far is not None:
            metrics["eval/FAR"] = far
        if frr is not None:
            metrics["eval/FRR"] = frr
        if latency_ms is not None:
            metrics["eval/latency_ms"] = latency_ms
        if extra:
            metrics.update({f"eval/{k}": v for k, v in extra.items()})
        if metrics:
            mlflow.log_metrics(metrics, step=step)

    def log_dataset_version(
        self,
        name: str,
        version: str,
        split: str,
        n_samples: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log dataset metadata as MLflow params.

        Args:
            name:      Dataset name e.g. 'ff++', 'custom_v1'
            version:   DVC/tag version string e.g. 'v1.0'
            split:     Split used e.g. 'train', 'val', 'test'
            n_samples: Number of samples in this split
            extra:     Additional dataset metadata
        """
        params: Dict[str, Any] = {
            f"dataset/{name}/version": version,
            f"dataset/{name}/split": split,
            f"dataset/{name}/n_samples": n_samples,
        }
        if extra:
            for k, v in extra.items():
                params[f"dataset/{name}/{k}"] = v
        mlflow.log_params(params)

    def log_artifact_path(self, local_path: str) -> None:
        """Log a local file or directory as an MLflow artifact."""
        mlflow.log_artifact(local_path)

    def log_tag(self, key: str, value: str) -> None:
        """Log a single tag on the active run."""
        mlflow.set_tag(key, value)


# ---------------------------------------------------------------------------
# Convenience: list all runs for an experiment
# ---------------------------------------------------------------------------

def list_runs(experiment: str) -> None:
    """Print a summary table of all runs in the given experiment."""
    mlflow.set_tracking_uri(TRACKING_URI)
    exp = mlflow.get_experiment_by_name(experiment)
    if exp is None:
        print(f"[tracker] No experiment named '{experiment}' found.")
        return
    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
    if runs.empty:
        print(f"[tracker] No runs found in experiment '{experiment}'.")
        return
    cols = ["tags.mlflow.runName", "metrics.eval/FAR", "metrics.eval/FRR",
            "metrics.eval/latency_ms", "tags.run_status", "start_time"]
    display_cols = [c for c in cols if c in runs.columns]
    print(f"\n[tracker] Runs in experiment '{experiment}':")
    print(runs[display_cols].to_string(index=False))
