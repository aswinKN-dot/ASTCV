"""
data/validator.py
-----------------
CLI validation tool for ASTCV session manifests.

Usage:
    # Validate a single session folder
    python -m data.validator data/raw/custom/<session_id>/

    # Validate all sessions under a directory
    python -m data.validator data/raw/custom/

    # Validate with frame file existence check
    python -m data.validator data/raw/custom/<session_id>/ --check-frames

    # Validate against a known challenge pattern registry
    python -m data.validator data/raw/custom/ --patterns data/manifests/challenge_patterns.json

    # Output a JSON report instead of human-readable
    python -m data.validator data/raw/custom/ --json

Owner: M3 (Aswin K N)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from pydantic import ValidationError

from data.schemas import SessionManifest

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    session_path: Path
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_path": str(self.session_path),
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

def _load_challenge_registry(patterns_path: Optional[Path]) -> Optional[set]:
    """
    Load the set of valid pattern IDs from the challenge registry JSON.
    Returns None if no registry is provided (pattern ID check is skipped).
    """
    if patterns_path is None:
        return None
    if not patterns_path.exists():
        print(f"[WARNING] Pattern registry not found at {patterns_path}. "
              f"Pattern ID registry check will be skipped.", file=sys.stderr)
        return None
    with patterns_path.open() as f:
        data = json.load(f)
    entries = data.get("patterns", data) if isinstance(data, dict) else data
    return {entry["pattern_id"] for entry in entries}


def _check_frame_files(
    session_path: Path,
    manifest: SessionManifest,
    result: ValidationResult,
) -> None:
    """
    Verify that every frame referenced in frame_timestamp_log has a
    corresponding JPEG file on disk:
    <session_path>/frames/frame_<NNNNNN>.jpg
    """
    frames_dir = session_path / "frames"
    if not frames_dir.exists():
        result.errors.append(
            f"frames/ directory not found at {frames_dir}. "
            f"Expected frame files to be stored there."
        )
        result.passed = False
        return

    missing = []
    for entry in manifest.frame_timestamp_log:
        expected_file = frames_dir / f"frame_{entry.frame_index:06d}.jpg"
        if not expected_file.exists():
            missing.append(str(expected_file))

    if missing:
        result.passed = False
        for m in missing[:10]:  # cap output to first 10 missing files
            result.errors.append(f"Missing frame file: {m}")
        if len(missing) > 10:
            result.errors.append(f"... and {len(missing) - 10} more missing frame files.")
    else:
        # Also check for unexpected extra frames
        actual_files = set(frames_dir.glob("frame_*.jpg"))
        expected_files = {
            frames_dir / f"frame_{e.frame_index:06d}.jpg"
            for e in manifest.frame_timestamp_log
        }
        extra = actual_files - expected_files
        if extra:
            result.warnings.append(
                f"{len(extra)} frame file(s) on disk not referenced in manifest. "
                f"First: {sorted(extra)[0].name}"
            )


def _check_registry_patterns(
    manifest: SessionManifest,
    registry: set,
    result: ValidationResult,
) -> None:
    """
    Verify that all pattern IDs used in this session exist in the
    challenge pattern registry loaded from challenge_patterns.json.
    """
    used = set(manifest.challenge_pattern_ids)
    unknown = used - registry
    if unknown:
        result.passed = False
        result.errors.append(
            f"challenge_pattern_ids contains IDs not found in the registry: {unknown}"
        )


def _check_consent_record_file(
    session_path: Path,
    manifest: SessionManifest,
    result: ValidationResult,
    consent_dir: Optional[Path] = None,
) -> None:
    """
    If consent_flag is True, verify that:
    1. consent_record_id is valid and non-nil.
    2. The physical signed PDF file exists in docs/consent_records/<consent_record_id>.pdf.
    """
    if manifest.consent_flag and manifest.consent_record_id is not None:
        nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
        if manifest.consent_record_id == nil_uuid:
            result.passed = False
            result.errors.append(
                "consent_record_id is a nil UUID (all zeros). "
                "This is not a valid consent record ID."
            )
            return

        # Check physical signed PDF
        target_dir = consent_dir or (Path(__file__).resolve().parent.parent / "docs" / "consent_records")
        expected_pdf = target_dir / f"{manifest.consent_record_id}.pdf"
        if not expected_pdf.exists():
            result.passed = False
            result.errors.append(
                f"Consent record PDF not found on disk: {expected_pdf}. "
                f"Every consent_record_id must be backed by a physical signed form."
            )


def validate_session(
    session_path: Path,
    check_frames: bool = False,
    pattern_registry: Optional[set] = None,
) -> ValidationResult:
    """
    Validate a single session directory.

    Args:
        session_path: Path to the session folder containing manifest.json
        check_frames: If True, verify frame files exist on disk
        pattern_registry: Set of valid pattern IDs from registry (or None to skip)

    Returns:
        ValidationResult with pass/fail status, errors, and warnings
    """
    result = ValidationResult(session_path=session_path, passed=True)

    # 1. Check manifest.json exists
    manifest_path = session_path / "manifest.json"
    if not manifest_path.exists():
        result.passed = False
        result.errors.append(f"manifest.json not found in {session_path}")
        return result

    # 2. Load and parse JSON
    try:
        with manifest_path.open() as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        result.passed = False
        result.errors.append(f"manifest.json is not valid JSON: {e}")
        return result

    # 3. Validate against Pydantic schema (covers all cross-field rules)
    try:
        manifest = SessionManifest(**raw)
    except ValidationError as e:
        result.passed = False
        for err in e.errors():
            loc = " → ".join(str(x) for x in err["loc"]) if err["loc"] else "root"
            result.errors.append(f"[{loc}] {err['msg']}")
        return result

    # 4. Check session_id matches folder name (optional but good practice)
    if session_path.name != str(manifest.session_id):
        result.warnings.append(
            f"Folder name '{session_path.name}' does not match "
            f"session_id '{manifest.session_id}'. Consider renaming."
        )

    # 5. Consent record sanity check
    _check_consent_record_file(session_path, manifest, result)

    # 6. Frame file existence check (optional)
    if check_frames:
        _check_frame_files(session_path, manifest, result)

    # 7. Pattern registry check (optional)
    if pattern_registry is not None:
        _check_registry_patterns(manifest, pattern_registry, result)

    return result


def validate_directory(
    root_path: Path,
    check_frames: bool = False,
    pattern_registry: Optional[set] = None,
) -> List[ValidationResult]:
    """
    Validate all session subdirectories under root_path.
    Each subdirectory that contains a manifest.json is treated as a session.
    """
    sessions = [
        p for p in root_path.iterdir()
        if p.is_dir() and (p / "manifest.json").exists()
    ]
    if not sessions:
        print(f"[WARNING] No session directories with manifest.json found under {root_path}")
        return []

    return [
        validate_session(s, check_frames=check_frames, pattern_registry=pattern_registry)
        for s in sorted(sessions)
    ]


# ---------------------------------------------------------------------------
# CLI output helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"


def _print_result(result: ValidationResult) -> None:
    status = f"{GREEN}✔ PASS{RESET}" if result.passed else f"{RED}✘ FAIL{RESET}"
    print(f"\n{BOLD}{result.session_path.name}{RESET}  {status}")
    for err in result.errors:
        print(f"  {RED}ERROR:{RESET} {err}")
    for warn in result.warnings:
        print(f"  {YELLOW}WARN:{RESET}  {warn}")


def _print_summary(results: List[ValidationResult]) -> None:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\n{'─' * 50}")
    print(f"{BOLD}Summary:{RESET} {passed} passed, {failed} failed out of {len(results)} session(s)")
    if failed > 0:
        print(f"{RED}Validation FAILED — fix errors before committing to DVC.{RESET}")
    else:
        print(f"{GREEN}All sessions passed validation.{RESET}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASTCV Session Manifest Validator (M3 — data quality gate)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m data.validator data/raw/custom/
  python -m data.validator data/raw/custom/<session_id>/ --check-frames
  python -m data.validator data/raw/custom/ --patterns data/manifests/challenge_patterns.json
  python -m data.validator data/raw/custom/ --json
        """,
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a single session folder or a directory of session folders.",
    )
    parser.add_argument(
        "--check-frames",
        action="store_true",
        default=False,
        help="Also verify that all frame files referenced in the manifest exist on disk.",
    )
    parser.add_argument(
        "--patterns",
        type=Path,
        default=None,
        metavar="REGISTRY",
        help="Path to challenge_patterns.json to validate pattern IDs against the registry.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output a machine-readable JSON report instead of human-readable text.",
    )
    args = parser.parse_args()

    target: Path = args.path.resolve()

    if not target.exists():
        print(f"{RED}ERROR:{RESET} Path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    # Load pattern registry if provided
    registry = _load_challenge_registry(args.patterns)

    # Determine if target is a single session or a directory of sessions
    manifest_path = target / "manifest.json"
    if manifest_path.exists():
        results = [validate_session(target, check_frames=args.check_frames, pattern_registry=registry)]
    elif target.is_dir():
        results = validate_directory(target, check_frames=args.check_frames, pattern_registry=registry)
    else:
        print(f"{RED}ERROR:{RESET} {target} is not a directory.", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No sessions found to validate.")
        sys.exit(0)

    # Output
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for result in results:
            _print_result(result)
        _print_summary(results)

    # Exit code: 1 if any session failed
    if any(not r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
