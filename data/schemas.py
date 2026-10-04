"""
data/schemas.py
---------------
Pydantic v2 models for the ASTCV session manifest.

These schemas are the authoritative source of truth for what M2's capture
pipeline must emit, hardened for Phase 2 readiness.

Owner: M3 (Aswin K N)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SessionLabel(str, Enum):
    """Valid liveness and attack label types for a captured session."""
    LIVE = "live"
    REPLAY = "replay"
    PRINT = "print"
    VIRTUAL_CAM = "virtual_camera"
    DEEPFAKE = "deepfake"


class LightingCondition(str, Enum):
    """Standardized ambient illumination environment."""
    BRIGHT_INDOOR = "bright_indoor"
    DIM_INDOOR = "dim_indoor"
    NATURAL_OUTDOOR = "natural_outdoor"
    HARSH_SIDE_LIT = "harsh_side_lit"
    VARIABLE = "variable"


class Eyewear(str, Enum):
    """Subject eyewear state for reflectance verification."""
    NONE = "none"
    PRESCRIPTION_GLASSES = "prescription_glasses"
    SUNGLASSES = "sunglasses"
    TINTED_GLASSES = "tinted_glasses"


class ClockSource(str, Enum):
    """Clock source used for hardware and frame timestamps."""
    PERFORMANCE_NOW = "performance.now"
    REQUEST_VIDEO_FRAME_CALLBACK = "requestVideoFrameCallback"
    SYSTEM_MONOTONIC = "system_monotonic"
    SYSTEM_UTC = "system_utc"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class CameraSettings(BaseModel):
    """Sensor capture settings critical for reflectance modeling."""
    model_config = ConfigDict(extra="forbid")

    fps: float = Field(..., gt=0.0, description="Configured camera capture FPS.")
    resolution_w: int = Field(..., gt=0, description="Native capture frame width in pixels.")
    resolution_h: int = Field(..., gt=0, description="Native capture frame height in pixels.")
    exposure_locked: bool = Field(..., description="Whether auto-exposure was locked.")
    white_balance_locked: bool = Field(..., description="Whether auto white balance was locked.")


class ChallengeParams(BaseModel):
    """Challenge pattern generation parameters."""
    model_config = ConfigDict(extra="forbid")

    color_space: str = Field(default="sRGB", description="Target color space (e.g. sRGB, Display-P3).")
    intensity_min: float = Field(..., ge=0.0, le=1.0, description="Minimum pattern luminance [0.0, 1.0].")
    intensity_max: float = Field(..., ge=0.0, le=1.0, description="Maximum pattern luminance [0.0, 1.0].")
    flash_seed: int = Field(..., description="Random seed used by Amal's pattern generator.")


class PatternEventEntry(BaseModel):
    """Emitter-side log recording when each pattern appeared on screen."""
    model_config = ConfigDict(extra="forbid")

    pattern_id: str = Field(..., min_length=1, description="ID of challenge pattern emitted.")
    emit_timestamp_ms: float = Field(..., ge=0.0, description="Hardware timestamp when pattern was rendered.")
    duration_ms: float = Field(..., gt=0.0, description="Scheduled duration on screen in ms.")


class FrameTimestampEntry(BaseModel):
    """Receiver-side entry in the per-frame captured timestamp log."""
    model_config = ConfigDict(extra="forbid")

    frame_index: int = Field(..., ge=0, description="Zero-based index of frame in session sequence.")
    hardware_timestamp_ms: float = Field(
        ..., ge=0.0, description="Sub-millisecond hardware timestamp when frame was captured."
    )
    pattern_id: str = Field(
        ..., min_length=1, description="ID of active challenge pattern during frame exposure."
    )
    is_dropped: bool = Field(
        default=False, description="Whether this frame was dropped/skipped by the capture pipeline."
    )


# ---------------------------------------------------------------------------
# Root session manifest model
# ---------------------------------------------------------------------------

class SessionManifest(BaseModel):
    """
    Full schema for an ASTCV session manifest.
    Stored at: data/raw/custom/<session_id>/manifest.json
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.1.0", description="ASTCV session schema semantic version.")
    pipeline_git_commit: str = Field(..., min_length=7, description="Git commit hash of capture pipeline code.")
    session_id: UUID = Field(..., description="UUID v4 uniquely identifying this capture session.")
    subject_id: UUID = Field(
        ...,
        description="UUID identifying the human subject. For bona-fide sessions, matches consent_record_id."
    )
    source_session_id: Optional[UUID] = Field(
        default=None,
        description="For attack sessions (replay/print/deepfake), UUID of the bona-fide session used as source."
    )
    device_model: str = Field(..., min_length=1, description="e.g. 'Samsung Galaxy S23', 'Dell XPS 15'")
    os_browser: str = Field(..., min_length=1, description="e.g. 'Android 14 / Chrome 126'")
    capture_timestamp_utc: str = Field(
        ..., description="ISO 8601 UTC timestamp of session start with timezone offset."
    )
    clock_source: ClockSource = Field(..., description="Hardware/browser clock mechanism utilized.")
    camera_settings: CameraSettings = Field(..., description="Hardware sensor configurations.")
    lighting_condition: LightingCondition = Field(..., description="Environmental ambient lighting category.")
    eyewear: Eyewear = Field(..., description="Subject eyewear condition.")
    skin_tone: Optional[str] = Field(
        default=None,
        description="Optional self-reported skin tone classification (Fitzpatrick I-VI or Monk 1-10)."
    )
    challenge_params: ChallengeParams = Field(..., description="Challenge rendering configuration.")
    challenge_pattern_ids: List[str] = Field(
        ..., min_length=1, description="Ordered sequence of pattern IDs shown."
    )
    pattern_events: List[PatternEventEntry] = Field(
        ..., min_length=1, description="Emitter-side timestamps when patterns were rendered."
    )
    frame_timestamp_log: List[FrameTimestampEntry] = Field(
        ..., min_length=1, description="Receiver-side per-frame capture timestamps."
    )
    label: SessionLabel = Field(..., description="Liveness or spoof attack type.")
    consent_flag: bool = Field(
        ..., description="True only when a signed consent record exists for this human subject."
    )
    consent_record_id: Optional[UUID] = Field(
        default=None, description="UUID linking to signed consent form in docs/consent_records/."
    )
    consent_form_version: Optional[str] = Field(
        default=None, description="Version tag of consent form signed (e.g. 'v1.1')."
    )
    calibration_applied: bool = Field(
        ..., description="Whether display-camera calibration was executed prior to session."
    )
    calibration_version: Optional[str] = Field(
        default=None, description="Calibration model version (e.g. 'v1.2'). Required if calibration_applied=True."
    )
    notes: Optional[str] = Field(default=None, description="Optional annotations.")

    # ------------------------------------------------------------------
    # Field Validators
    # ------------------------------------------------------------------

    @field_validator("capture_timestamp_utc")
    @classmethod
    def require_tz_aware_iso8601(cls, v: str) -> str:
        """Validate that capture_timestamp_utc is a valid ISO 8601 string WITH timezone."""
        try:
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Timestamp must include an explicit timezone offset or 'Z'.")
        except Exception as e:
            raise ValueError(
                f"capture_timestamp_utc '{v}' is not a valid timezone-aware ISO 8601 string: {e}"
            )
        return v

    # ------------------------------------------------------------------
    # Model Validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_subject_and_source_identities(self) -> "SessionManifest":
        """Validate subject_id linkage and attack source_session_id inheritance."""
        if self.label == SessionLabel.LIVE:
            if self.consent_flag and self.consent_record_id:
                if self.subject_id != self.consent_record_id:
                    raise ValueError(
                        f"For bona-fide LIVE sessions, subject_id ({self.subject_id}) "
                        f"must match consent_record_id ({self.consent_record_id})."
                    )
        else:
            # Attack sessions (replay, print, virtual camera, deepfake)
            if self.source_session_id is None:
                raise ValueError(
                    f"Attack session with label '{self.label.value}' must provide a "
                    f"source_session_id identifying the bona-fide session it was generated from."
                )
        return self

    @model_validator(mode="after")
    def validate_consent_fields(self) -> "SessionManifest":
        """Ensure consent_record_id and consent_form_version accompany consent_flag=True."""
        if self.consent_flag:
            if self.consent_record_id is None:
                raise ValueError("consent_record_id must be provided when consent_flag is True.")
            if self.consent_form_version is None:
                raise ValueError("consent_form_version must be provided when consent_flag is True.")
        else:
            if self.consent_record_id is not None:
                raise ValueError("consent_record_id must be None when consent_flag is False.")
        return self

    @model_validator(mode="after")
    def validate_calibration_version(self) -> "SessionManifest":
        if self.calibration_applied and not self.calibration_version:
            raise ValueError("calibration_version is required when calibration_applied is True.")
        return self

    @model_validator(mode="after")
    def validate_frame_contiguity_and_monotonicity(self) -> "SessionManifest":
        """Verify frame indices are contiguous and capture timestamps strictly increase."""
        indices = [e.frame_index for e in self.frame_timestamp_log]
        if sorted(indices) != list(range(len(indices))):
            raise ValueError(
                f"frame_timestamp_log indices must be contiguous starting from 0. Got: {sorted(indices)}"
            )

        sorted_entries = sorted(self.frame_timestamp_log, key=lambda e: e.frame_index)
        for i in range(1, len(sorted_entries)):
            prev_ts = sorted_entries[i - 1].hardware_timestamp_ms
            curr_ts = sorted_entries[i].hardware_timestamp_ms
            if curr_ts <= prev_ts:
                raise ValueError(
                    f"Hardware timestamp not strictly increasing at frame {sorted_entries[i].frame_index}: "
                    f"current {curr_ts}ms <= previous {prev_ts}ms."
                )
        return self

    @model_validator(mode="after")
    def validate_pattern_order_and_continuity(self) -> "SessionManifest":
        """
        Verify that:
        1. All pattern_ids in frame_timestamp_log and pattern_events are declared.
        2. Patterns in frame_timestamp_log follow the ordered sequence in challenge_pattern_ids.
        """
        declared_order = self.challenge_pattern_ids
        declared_set = set(declared_order)

        # Verify pattern_events
        event_patterns = {pe.pattern_id for pe in self.pattern_events}
        if not event_patterns.issubset(declared_set):
            raise ValueError(
                f"pattern_events contains undeclared pattern IDs: {event_patterns - declared_set}"
            )

        # Verify frame log sequence order
        observed_sequence: List[str] = []
        last_pattern: Optional[str] = None
        for entry in self.frame_timestamp_log:
            pid = entry.pattern_id
            if pid not in declared_set:
                raise ValueError(f"frame_timestamp_log references undeclared pattern ID '{pid}'.")
            if pid != last_pattern:
                observed_sequence.append(pid)
                last_pattern = pid

        # Check observed pattern transitions match declared order
        if observed_sequence != declared_order:
            raise ValueError(
                f"Pattern transition sequence in frame_timestamp_log does not match declared challenge_pattern_ids.\n"
                f"Declared: {declared_order}\n"
                f"Observed: {observed_sequence}"
            )

        return self
