"""
data/schemas.py
---------------
Pydantic v2 models for the ASTCV session manifest.

These schemas are the authoritative source of truth for what M2's capture
pipeline must emit. They are derived from docs/data_contract.md.

Owner: M3 (Aswin K N)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SessionLabel(str, Enum):
    """Valid liveness label types for a captured session."""
    LIVE          = "live"
    REPLAY        = "replay"
    PRINT         = "print"
    VIRTUAL_CAM   = "virtual_camera"
    DEEPFAKE      = "deepfake"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class FrameTimestampEntry(BaseModel):
    """Single entry in the per-frame timestamp log."""

    frame_index: int = Field(..., ge=0, description="Zero-based frame index.")
    hardware_timestamp_ms: int = Field(
        ..., ge=0,
        description="Milliseconds since session start, from hardware clock."
    )
    pattern_id: str = Field(
        ..., min_length=1,
        description="ID of the challenge pattern active at this frame."
    )


# ---------------------------------------------------------------------------
# Root session manifest model
# ---------------------------------------------------------------------------

class SessionManifest(BaseModel):
    """
    Full schema for a captured session manifest.
    Stored at: data/raw/custom/<session_id>/manifest.json
    """

    session_id: UUID = Field(..., description="UUID v4 uniquely identifying this session.")
    device_model: str = Field(..., min_length=1, description="e.g. 'Samsung Galaxy S23'")
    os_browser: str = Field(..., min_length=1, description="e.g. 'Android 14 / Chrome 126'")
    capture_timestamp_utc: str = Field(
        ...,
        description="ISO 8601 UTC timestamp of session start. e.g. '2026-10-05T08:00:00Z'"
    )
    challenge_pattern_ids: List[str] = Field(
        ..., min_length=1,
        description="Ordered list of pattern IDs shown during the session."
    )
    frame_timestamp_log: List[FrameTimestampEntry] = Field(
        ..., min_length=1,
        description="Per-frame hardware timestamp and active pattern ID."
    )
    label: SessionLabel = Field(..., description="Liveness label for the session.")
    consent_flag: bool = Field(
        ...,
        description="True only when a signed consent record exists for this subject."
    )
    consent_record_id: Optional[UUID] = Field(
        default=None,
        description="UUID linking to the signed consent form in docs/consent_records/."
    )
    calibration_applied: bool = Field(
        ...,
        description="Whether display-camera calibration was run before this session."
    )
    calibration_version: Optional[str] = Field(
        default=None,
        description="e.g. 'v1.2'. Required when calibration_applied is True."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional free-text notes e.g. 'subject wore glasses'."
    )

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def consent_record_required_when_flag_true(self) -> "SessionManifest":
        """consent_record_id must be present whenever consent_flag is True."""
        if self.consent_flag and self.consent_record_id is None:
            raise ValueError(
                "consent_record_id must be set when consent_flag is True. "
                "Do not mark consent_flag=True without a signed consent form on file."
            )
        if not self.consent_flag and self.consent_record_id is not None:
            raise ValueError(
                "consent_record_id is set but consent_flag is False. "
                "Either set consent_flag=True or remove consent_record_id."
            )
        return self

    @model_validator(mode="after")
    def calibration_version_required_when_applied(self) -> "SessionManifest":
        """calibration_version must be set when calibration_applied is True."""
        if self.calibration_applied and not self.calibration_version:
            raise ValueError(
                "calibration_version must be specified when calibration_applied is True."
            )
        return self

    @model_validator(mode="after")
    def frame_indices_are_contiguous(self) -> "SessionManifest":
        """frame_timestamp_log entries must have contiguous zero-based indices."""
        indices = [e.frame_index for e in self.frame_timestamp_log]
        expected = list(range(len(indices)))
        if sorted(indices) != expected:
            raise ValueError(
                f"frame_timestamp_log indices are not contiguous starting from 0. "
                f"Got indices: {sorted(indices)}"
            )
        return self

    @model_validator(mode="after")
    def timestamps_are_monotonically_increasing(self) -> "SessionManifest":
        """Hardware timestamps must strictly increase — no backwards jumps."""
        sorted_entries = sorted(self.frame_timestamp_log, key=lambda e: e.frame_index)
        for i in range(1, len(sorted_entries)):
            prev = sorted_entries[i - 1].hardware_timestamp_ms
            curr = sorted_entries[i].hardware_timestamp_ms
            if curr <= prev:
                raise ValueError(
                    f"Timestamp not monotonically increasing at frame {sorted_entries[i].frame_index}: "
                    f"timestamp {curr}ms is not greater than previous {prev}ms."
                )
        return self

    @model_validator(mode="after")
    def pattern_ids_in_log_match_declared_ids(self) -> "SessionManifest":
        """
        Every pattern_id referenced in frame_timestamp_log must appear
        in challenge_pattern_ids. Catches pipeline bugs where emitted
        pattern IDs diverge from the declared sequence.
        """
        declared = set(self.challenge_pattern_ids)
        used = {e.pattern_id for e in self.frame_timestamp_log}
        unknown = used - declared
        if unknown:
            raise ValueError(
                f"frame_timestamp_log references pattern IDs not declared in "
                f"challenge_pattern_ids: {unknown}"
            )
        return self

    @field_validator("capture_timestamp_utc")
    @classmethod
    def capture_timestamp_is_iso8601(cls, v: str) -> str:
        """Validate that capture_timestamp_utc is a parseable ISO 8601 string."""
        from datetime import datetime
        try:
            # Support both Z suffix and +00:00 offset
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(
                f"capture_timestamp_utc '{v}' is not a valid ISO 8601 timestamp. "
                f"Expected format: '2026-10-05T08:00:00Z'"
            )
        return v
