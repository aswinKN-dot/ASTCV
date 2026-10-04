"""
scripts/preprocess/extract_frames.py
-----------------------------------
Standardized video frame extraction utility for ASTCV.

Extracts frames from video files into standardized zero-padded JPG files
(frame_000000.jpg, frame_000001.jpg, ...) with extraction manifests.

Features:
- Preserves native resolution by default (or optional max dimension resizing)
- Configurable sampling rate: extract every Nth frame, specific target FPS, or all native frames
- Idempotent: skips already extracted videos unless --force is specified
- Generates a per-video extraction summary manifest with MD5 hash, duration, and frame metadata

Owner: M3 (Aswin K N)

Usage:
    # Extract all frames from a single video
    python scripts/preprocess/extract_frames.py --input path/to/video.mp4 --output-dir data/processed/extracted/

    # Extract at 5 FPS from all videos in a directory
    python scripts/preprocess/extract_frames.py --input-dir data/raw/public/uadfv/ --output-dir data/processed/uadfv_frames/ --fps 5

    # Extract up to 100 frames per video
    python scripts/preprocess/extract_frames.py --input-dir data/raw/public/ --output-dir data/processed/frames/ --max-frames 100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("extract_frames")


def compute_file_hash(filepath: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file for integrity tracking."""
    sha256 = hashlib.sha256()
    with filepath.open("rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_video_frames(
    video_path: Path,
    output_dir: Path,
    target_fps: Optional[float] = None,
    max_frames: Optional[int] = None,
    jpeg_quality: int = 95,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Extract frames from a single video file.

    Args:
        video_path: Path to input video file.
        output_dir: Directory where extracted frames and manifest will be stored.
        target_fps: Target extraction rate (frames per second). If None, extract all frames.
        max_frames: Maximum number of frames to extract. If None, extract all available.
        jpeg_quality: JPEG compression quality (1-100).
        force: Overwrite existing frames if True.

    Returns:
        Dictionary containing extraction metadata and statistics.
    """
    video_id = video_path.stem
    target_video_dir = output_dir / video_id
    frames_dir = target_video_dir / "frames"
    manifest_path = target_video_dir / "extraction_manifest.json"

    if manifest_path.exists() and not force:
        logger.info(f"Skipping already extracted video: {video_path.name} (use --force to overwrite)")
        with manifest_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    target_video_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video file: {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_native_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec = total_native_frames / native_fps if native_fps > 0 else 0.0

    # Calculate frame step based on target FPS
    if target_fps is not None and target_fps > 0 and target_fps < native_fps:
        frame_interval = native_fps / target_fps
    else:
        frame_interval = 1.0

    extracted_frames_info: List[Dict[str, Any]] = []
    frame_idx = 0
    next_sample_frame = 0.0
    saved_count = 0

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx >= int(round(next_sample_frame)):
            out_filename = f"frame_{saved_count:06d}.jpg"
            out_path = frames_dir / out_filename
            cv2.imwrite(str(out_path), frame, encode_params)

            timestamp_ms = int(round((frame_idx / native_fps) * 1000.0))
            extracted_frames_info.append({
                "frame_index": saved_count,
                "source_frame_index": frame_idx,
                "timestamp_ms": timestamp_ms,
                "filename": out_filename,
            })

            saved_count += 1
            next_sample_frame += frame_interval

            if max_frames is not None and saved_count >= max_frames:
                break

        frame_idx += 1

    cap.release()

    video_sha256 = compute_file_hash(video_path)

    manifest_data = {
        "video_filename": video_path.name,
        "source_path": str(video_path.resolve()),
        "source_sha256": video_sha256,
        "native_width": width,
        "native_height": height,
        "native_fps": round(native_fps, 2),
        "total_native_frames": total_native_frames,
        "duration_sec": round(duration_sec, 2),
        "extracted_fps": target_fps if target_fps else round(native_fps, 2),
        "extracted_frame_count": saved_count,
        "frames": extracted_frames_info,
    }

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    logger.info(
        f"Extracted {saved_count} frames from {video_path.name} "
        f"({width}x{height} @ {native_fps:.1f}fps -> {target_video_dir})"
    )
    return manifest_data


def process_directory(
    input_dir: Path,
    output_dir: Path,
    extensions: tuple = (".mp4", ".avi", ".mov", ".mkv", ".webm"),
    target_fps: Optional[float] = None,
    max_frames: Optional[int] = None,
    jpeg_quality: int = 95,
    force: bool = False,
) -> None:
    """Process all video files matching supported extensions in input_dir."""
    video_files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in extensions]
    if not video_files:
        logger.warning(f"No video files with extensions {extensions} found in {input_dir}")
        return

    logger.info(f"Found {len(video_files)} video(s) in {input_dir}")
    success_count = 0
    failure_count = 0

    for idx, vpath in enumerate(video_files, start=1):
        try:
            logger.info(f"[{idx}/{len(video_files)}] Processing {vpath.name}...")
            extract_video_frames(
                video_path=vpath,
                output_dir=output_dir,
                target_fps=target_fps,
                max_frames=max_frames,
                jpeg_quality=jpeg_quality,
                force=force,
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to process {vpath}: {e}")
            failure_count += 1

    logger.info(f"Extraction complete: {success_count} succeeded, {failure_count} failed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standardized frame extraction tool for ASTCV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="Path to single input video file.")
    group.add_argument("--input-dir", type=Path, help="Directory containing videos to process recursively.")

    parser.add_argument("--output-dir", type=Path, required=True, help="Destination directory for processed frames.")
    parser.add_argument("--fps", type=float, default=None, help="Target extraction FPS (extracts all frames if omitted).")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to extract per video.")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality level (1-100).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing extracted frames.")

    args = parser.parse_args()

    if args.input:
        if not args.input.exists() or not args.input.is_file():
            logger.error(f"Input file does not exist: {args.input}")
            sys.exit(1)
        extract_video_frames(
            video_path=args.input,
            output_dir=args.output_dir,
            target_fps=args.fps,
            max_frames=args.max_frames,
            jpeg_quality=args.quality,
            force=args.force,
        )
    elif args.input_dir:
        if not args.input_dir.exists() or not args.input_dir.is_dir():
            logger.error(f"Input directory does not exist: {args.input_dir}")
            sys.exit(1)
        process_directory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            target_fps=args.fps,
            max_frames=args.max_frames,
            jpeg_quality=args.quality,
            force=args.force,
        )


if __name__ == "__main__":
    main()
