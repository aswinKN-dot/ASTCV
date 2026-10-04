"""
eval/jitter_analysis.py
-----------------------
Cross-device synchronization jitter analysis and MLflow benchmarking tool.

Computes statistical distribution of transmission and hardware-timestamp jitter
across tested devices (phones, laptops) and verifies synchronization bounds.

Key metrics (namespaced under 'sync/'):
- sync/delta_mean_ms & sync/delta_median_ms
- sync/delta_std_ms (latency spread standard deviation)
- sync/spread_p95_p5_ms (P95 - P5 latency spread)
- sync/mean_interval_jitter_ms (computed strictly between consecutive captured frames)
- sync/max_jitter_spike_ms
- sync/drop_rate_pct
- sync/timing_error_exceed_fraction (fraction of frames exceeding 20% of nominal challenge period)

Note on display quantization:
  Screen pattern emissions only update at display VSYNC boundaries. At 60 Hz,
  an unavoidable quantization uncertainty of up to 16.67 ms (8.33 ms at 120 Hz)
  is physically present in emitter timestamps.

Owner: M3 (Aswin K N)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import mlflow
import numpy as np

from data.schemas_jitter import JitterTestLog
from eval.tracker import ASTCVRun, TRACKING_URI, make_run_name, setup_experiment, today_str

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("jitter_analysis")

# Synchronization tolerance: error exceeding 20% of nominal challenge period is flagged
TIMING_ERROR_THRESHOLD_RATIO = 0.20


def compute_jitter_metrics(log: JitterTestLog) -> Dict[str, Any]:
    """Calculate statistical latency, interval jitter, and synchronization bounds."""
    total_samples = len(log.samples)
    dropped_count = sum(1 for s in log.samples if s.is_dropped)
    drop_rate = (dropped_count / total_samples) * 100.0 if total_samples > 0 else 0.0

    # Samples with valid captures
    captured_samples = [s for s in log.samples if not s.is_dropped and s.delta_ms is not None]

    base_result: Dict[str, Any] = {
        "test_id": str(log.test_id),
        "device_model": log.device_model,
        "device_type": log.device_type.value,
        "os_browser": log.os_browser,
        "clock_domain": log.clock_domain.value,
        "network_condition": log.network_condition.value,
        "camera_fps": log.camera_fps,
        "display_refresh_rate_hz": log.display_refresh_rate_hz,
        "nominal_challenge_period_ms": log.nominal_challenge_period_ms,
        "total_frames": total_samples,
        "dropped_frames": dropped_count,
        "drop_rate_pct": round(drop_rate, 2),
    }

    # Handle fully dropped test
    if not captured_samples:
        logger.warning(f"Device {log.device_model} (test {log.test_id}) dropped 100% of frames!")
        base_result.update({
            "is_fully_dropped": True,
            "mean_latency_ms": None,
            "median_latency_ms": None,
            "std_latency_ms": None,
            "spread_p95_p5_ms": None,
            "mean_interval_jitter_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "max_latency_ms": None,
            "timing_error_exceed_fraction": 1.0,
            "vsync_period_ms": round(1000.0 / log.display_refresh_rate_hz, 2),
        })
        return base_result

    # Sample size warnings for tail percentiles
    n_captured = len(captured_samples)
    if n_captured < 100:
        logger.warning(
            f"Sample size ({n_captured}) < 100: P95 latency estimate may have high variance."
        )
    if n_captured < 1000:
        logger.warning(
            f"Sample size ({n_captured}) < 1000: P99 latency estimate is unreliable."
        )

    deltas = np.array([s.delta_ms for s in captured_samples], dtype=np.float64)

    # Compute interval jitter ONLY across consecutive frame indices (ignoring gaps from drops)
    interval_jitters: List[float] = []
    measured_intervals: List[float] = []
    expected_interval_ms = 1000.0 / log.camera_fps

    for i in range(len(captured_samples) - 1):
        curr_s = captured_samples[i]
        next_s = captured_samples[i + 1]
        # Only compare if frame indices are strictly consecutive (no dropped frame in between)
        if next_s.frame_index == curr_s.frame_index + 1:
            interval = next_s.capture_timestamp_ms - curr_s.capture_timestamp_ms
            measured_intervals.append(interval)
            interval_jitters.append(abs(interval - expected_interval_ms))

    mean_interval_jitter = float(np.mean(interval_jitters)) if interval_jitters else 0.0
    max_interval_jitter = float(np.max(interval_jitters)) if interval_jitters else 0.0
    measured_median_interval = float(np.median(measured_intervals)) if measured_intervals else expected_interval_ms

    mean_delta = float(np.mean(deltas))
    median_delta = float(np.median(deltas))
    std_delta = float(np.std(deltas))
    p5_delta = float(np.percentile(deltas, 5))
    p95_delta = float(np.percentile(deltas, 95))
    p99_delta = float(np.percentile(deltas, 99))
    min_delta = float(np.min(deltas))
    max_delta = float(np.max(deltas))
    spread_p95_p5 = float(p95_delta - p5_delta)

    # Timing error relative to nominal challenge period (variation around median delay)
    timing_errors = np.abs(deltas - median_delta)
    max_allowed_error = log.nominal_challenge_period_ms * TIMING_ERROR_THRESHOLD_RATIO
    exceed_count = int(np.sum(timing_errors > max_allowed_error))
    exceed_fraction = float(exceed_count / n_captured)

    vsync_period = 1000.0 / log.display_refresh_rate_hz

    base_result.update({
        "is_fully_dropped": False,
        "mean_latency_ms": round(mean_delta, 2),
        "median_latency_ms": round(median_delta, 2),
        "std_latency_ms": round(std_delta, 2),
        "p5_latency_ms": round(p5_delta, 2),
        "p95_latency_ms": round(p95_delta, 2),
        "p99_latency_ms": round(p99_delta, 2),
        "min_latency_ms": round(min_delta, 2),
        "max_latency_ms": round(max_delta, 2),
        "spread_p95_p5_ms": round(spread_p95_p5, 2),
        "measured_median_interval_ms": round(measured_median_interval, 2),
        "mean_interval_jitter_ms": round(mean_interval_jitter, 2),
        "max_jitter_spike_ms": round(max_interval_jitter, 2),
        "timing_error_exceed_fraction": round(exceed_fraction, 4),
        "vsync_period_ms": round(vsync_period, 2),
    })
    return base_result


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
        "Net",
        "Frames",
        "Drop %",
        "Median (ms)",
        "Spread P95-P5",
        "Interval Jitter",
        "Err > 20% Period",
    ]
    rows = []
    for r in results:
        if r.get("is_fully_dropped", False):
            rows.append([
                r["device_model"][:16],
                r["network_condition"][:10],
                str(r["total_frames"]),
                "100.0%",
                "DROPPED",
                "DROPPED",
                "DROPPED",
                "100.0%",
            ])
        else:
            rows.append([
                r["device_model"][:16],
                r["network_condition"][:10],
                str(r["total_frames"]),
                f"{r['drop_rate_pct']:.1f}%",
                f"{r['median_latency_ms']:.1f}",
                f"{r['spread_p95_p5_ms']:.1f}",
                f"{r['mean_interval_jitter_ms']:.1f}",
                f"{r['timing_error_exceed_fraction'] * 100:.1f}%",
            ])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    sep_line = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    header_line = "| " + " | ".join([h.ljust(col_widths[i]) for i, h in enumerate(headers)]) + " |"

    formatted_rows = [sep_line, header_line, sep_line]
    for row in rows:
        formatted_rows.append(
            "| " + " | ".join([val.ljust(col_widths[i]) for i, val in enumerate(row)]) + " |"
        )
    formatted_rows.append(sep_line)
    return "\n".join(formatted_rows)


def log_results_to_mlflow(results: List[Dict[str, Any]]) -> None:
    """Log individual jitter benchmark test results into MLflow with deduplication."""
    experiment_name = "phase1_jitter_benchmark"
    setup_experiment(experiment_name)
    mlflow.set_tracking_uri(TRACKING_URI)

    # Search existing runs to prevent duplicate logging of the same test_id
    existing_runs = mlflow.search_runs(experiment_names=[experiment_name])
    existing_test_ids = set()
    if not existing_runs.empty and "tags.test_id" in existing_runs.columns:
        existing_test_ids = set(existing_runs["tags.test_id"].dropna().tolist())

    for r in results:
        test_id = r["test_id"]
        if test_id in existing_test_ids:
            logger.info(f"Skipping already-logged jitter test_id '{test_id}' in MLflow.")
            continue

        clean_device = r["device_model"].lower().replace(" ", "").replace("-", "")
        clean_net = r["network_condition"].lower().replace("_", "")
        run_name = f"{clean_device}_{clean_net}_{today_str()}"

        tags = {
            "device_type": r["device_type"],
            "network": r["network_condition"],
            "test_id": test_id,
            "clock_domain": r["clock_domain"],
        }

        with ASTCVRun(
            experiment=experiment_name,
            run_name=run_name,
            dataset="jitter_benchmark",
            device=r["device_model"],
            tags=tags,
        ) as run:
            run.log_params({
                "camera_fps": r["camera_fps"],
                "display_refresh_rate_hz": r["display_refresh_rate_hz"],
                "os_browser": r["os_browser"],
                "nominal_challenge_period_ms": r["nominal_challenge_period_ms"],
                "vsync_period_ms": r["vsync_period_ms"],
            })

            # Namespace ALL synchronization metrics under sync/
            sync_metrics: Dict[str, float] = {
                "sync/drop_rate_pct": r["drop_rate_pct"],
                "sync/timing_error_exceed_fraction": r["timing_error_exceed_fraction"],
            }
            if not r.get("is_fully_dropped", False):
                sync_metrics.update({
                    "sync/delta_mean_ms": r["mean_latency_ms"],
                    "sync/delta_median_ms": r["median_latency_ms"],
                    "sync/delta_std_ms": r["std_latency_ms"],
                    "sync/spread_p95_p5_ms": r["spread_p95_p5_ms"],
                    "sync/p95_delta_ms": r["p95_latency_ms"],
                    "sync/p99_delta_ms": r["p99_latency_ms"],
                    "sync/max_delta_ms": r["max_latency_ms"],
                    "sync/mean_interval_jitter_ms": r["mean_interval_jitter_ms"],
                    "sync/max_jitter_spike_ms": r["max_jitter_spike_ms"],
                })

            mlflow.log_metrics(sync_metrics)
            logger.info(f"Logged jitter benchmarks for '{r['device_model']}' under run '{run_name}'")


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
