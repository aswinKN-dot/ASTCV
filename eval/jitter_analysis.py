"""
eval/jitter_analysis.py
-----------------------
Cross-device synchronization jitter analysis and MLflow benchmarking tool.

Computes statistical distribution of transmission and hardware-timestamp jitter
across tested devices (phones, laptops) and verifies synchronization bounds.

Key metrics:
- Mean latency (ms) & Median latency (ms)
- Standard deviation of latency (jitter metric)
- 95th and 99th percentile latencies (P95, P99)
- Maximum jitter spike (ms)
- Frame drop rate (%)

Owner: M3 (Aswin K N)

Usage:
    # Analyze a single device jitter log
    python eval/jitter_analysis.py data/raw/jitter_tests/<test_id>/jitter_log.json

    # Analyze and compare all jitter tests in directory
    python eval/jitter_analysis.py data/raw/jitter_tests/

    # Log metrics directly to MLflow experiment 'phase1_jitter_benchmark'
    python eval/jitter_analysis.py data/raw/jitter_tests/ --log-mlflow
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

from data.schemas_jitter import JitterTestLog
from eval.tracker import ASTCVRun, make_run_name, setup_experiment

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("jitter_analysis")


def compute_jitter_metrics(log: JitterTestLog) -> Dict[str, Any]:
    """Calculate statistical latency and jitter metrics from a validated test log."""
    valid_samples = [s for s in log.samples if not s.is_dropped]
    total_samples = len(log.samples)
    dropped_count = total_samples - len(valid_samples)
    drop_rate = (dropped_count / total_samples) * 100.0 if total_samples > 0 else 0.0

    if not valid_samples:
        return {
            "test_id": str(log.test_id),
            "device_model": log.device_model,
            "device_type": log.device_type.value,
            "total_frames": total_samples,
            "dropped_frames": dropped_count,
            "drop_rate_pct": drop_rate,
            "error": "All frames dropped",
        }

    deltas = np.array([s.delta_ms for s in valid_samples], dtype=np.float64)

    # Frame interval jitter (delta between successive capture timestamps vs expected interval)
    capture_ts = np.array([s.capture_timestamp_ms for s in valid_samples], dtype=np.float64)
    if len(capture_ts) > 1:
        inter_frame_intervals = np.diff(capture_ts)
        expected_interval = 1000.0 / log.camera_fps
        interval_jitter = np.abs(inter_frame_intervals - expected_interval)
        mean_jitter = float(np.mean(interval_jitter))
        max_jitter = float(np.max(interval_jitter))
    else:
        mean_jitter = 0.0
        max_jitter = 0.0

    mean_latency = float(np.mean(deltas))
    median_latency = float(np.median(deltas))
    std_latency = float(np.std(deltas))
    p95_latency = float(np.percentile(deltas, 95))
    p99_latency = float(np.percentile(deltas, 99))
    min_latency = float(np.min(deltas))
    max_latency = float(np.max(deltas))

    return {
        "test_id": str(log.test_id),
        "device_model": log.device_model,
        "device_type": log.device_type.value,
        "os_browser": log.os_browser,
        "network_condition": log.network_condition.value,
        "camera_fps": log.camera_fps,
        "display_refresh_rate_hz": log.display_refresh_rate_hz,
        "total_frames": total_samples,
        "dropped_frames": dropped_count,
        "drop_rate_pct": round(drop_rate, 2),
        "mean_latency_ms": round(mean_latency, 2),
        "median_latency_ms": round(median_latency, 2),
        "std_latency_ms": round(std_latency, 2),
        "mean_interval_jitter_ms": round(mean_jitter, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "p99_latency_ms": round(p99_latency, 2),
        "min_latency_ms": round(min_latency, 2),
        "max_latency_ms": round(max_latency, 2),
        "max_jitter_spike_ms": round(max_jitter, 2),
    }


def analyze_log_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load, validate, and analyze a single jitter log file."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)
        validated_log = JitterTestLog(**raw_data)
        return compute_jitter_metrics(validated_log)
    except Exception as e:
        logger.error(f"Validation failed for {file_path}: {e}")
        return None


def format_summary_table(results: List[Dict[str, Any]]) -> str:
    """Format comparative results as a clean table."""
    headers = [
        "Device",
        "Type",
        "Net",
        "Frames",
        "Drop %",
        "Mean (ms)",
        "Std Dev",
        "P95 (ms)",
        "Max (ms)",
    ]
    rows = []
    for r in results:
        if "error" in r:
            continue
        rows.append([
            r["device_model"][:16],
            r["device_type"][:8],
            r["network_condition"][:10],
            str(r["total_frames"]),
            f"{r['drop_rate_pct']:.1f}%",
            f"{r['mean_latency_ms']:.1f}",
            f"{r['std_latency_ms']:.1f}",
            f"{r['p95_latency_ms']:.1f}",
            f"{r['max_latency_ms']:.1f}",
        ])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    sep_line = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    header_line = "| " + " | ".join([h.ljust(col_widths[i]) for i, h in enumerate(headers)]) + " |"

    formatted_rows = []
    for row in rows:
        formatted_rows.append(
            "| " + " | ".join([val.ljust(col_widths[i]) for i, val in enumerate(row)]) + " |"
        )

    return "\n".join([sep_line, header_line, sep_line] + formatted_rows + [sep_line])


def log_results_to_mlflow(results: List[Dict[str, Any]]) -> None:
    """Log individual jitter benchmark test results into MLflow."""
    experiment_name = "phase1_jitter_benchmark"
    setup_experiment(experiment_name)

    for r in results:
        if "error" in r:
            continue

        clean_device = r["device_model"].lower().replace(" ", "").replace("-", "")
        run_name = make_run_name(device=clean_device, dataset="jittertest")

        with ASTCVRun(
            experiment=experiment_name,
            run_name=run_name,
            dataset="jitter_benchmark",
            device=r["device_model"],
            tags={
                "device_type": r["device_type"],
                "network": r["network_condition"],
                "test_id": r["test_id"],
            },
        ) as run:
            run.log_params({
                "camera_fps": r["camera_fps"],
                "display_refresh_rate_hz": r["display_refresh_rate_hz"],
                "os_browser": r["os_browser"],
                "network_condition": r["network_condition"],
            })
            run.log_eval_metrics(
                latency_ms=r["mean_latency_ms"],
                extra={
                    "drop_rate_pct": r["drop_rate_pct"],
                    "std_latency_ms": r["std_latency_ms"],
                    "p95_latency_ms": r["p95_latency_ms"],
                    "p99_latency_ms": r["p99_latency_ms"],
                    "max_latency_ms": r["max_latency_ms"],
                    "mean_interval_jitter_ms": r["mean_interval_jitter_ms"],
                    "max_jitter_spike_ms": r["max_jitter_spike_ms"],
                },
            )
            logger.info(f"Logged jitter benchmarks for '{r['device_model']}' to MLflow run '{run_name}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASTCV Cross-Device Jitter Analysis Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("path", type=Path, help="Path to jitter_log.json or directory containing test logs.")
    parser.add_argument("--log-mlflow", action="store_true", help="Log benchmark metrics to MLflow.")
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")

    args = parser.parse_args()
    target_path = args.path.resolve()

    if not target_path.exists():
        logger.error(f"Path does not exist: {target_path}")
        sys.exit(1)

    if target_path.is_file():
        files_to_process = [target_path]
    else:
        files_to_process = sorted(list(target_path.rglob("jitter_log.json")))

    if not files_to_process:
        logger.warning(f"No 'jitter_log.json' files found in {target_path}")
        sys.exit(0)

    logger.info(f"Processing {len(files_to_process)} jitter test log(s)...")
    results = []
    for fp in files_to_process:
        res = analyze_log_file(fp)
        if res:
            results.append(res)

    if not results:
        logger.error("No valid test results to display.")
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n=== Cross-Device Jitter Synchronization Benchmark ===")
        print(format_summary_table(results))

    if args.log_mlflow:
        log_results_to_mlflow(results)


if __name__ == "__main__":
    main()
