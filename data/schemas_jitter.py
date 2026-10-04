"""
data/schemas_jitter.py
----------------------
Pydantic v2 schemas for Cross-Device Hardware-Timestamp Jitter Benchmark Logs.

Used by M3 to validate and store synchronization test logs produced by M1 (Amal)
and M2 (Abhijith) during Phase 1 cross-device synchronization testing.

Stored at: data/raw/jitter_tests/<test_id>/jitter_log.json

Owner: M3 (Aswin K N)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class DeviceType(str, Enum):
    MOBILE = "mobile"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"


class NetworkCondition(str, Enum):
    LOCAL = "local"
    WIFI_5GHZ = "wifi_5ghz"
    WIFI_2_4GHZ = "wifi_2.4ghz"
    CELLULAR_5G = "cellular_5g"
    CELLULAR_4G = "cellular_4g"
    SIMULATED_JITTER = "simulated_jitter"


class JitterSampleEntry(BaseModel):
    """Per-frame synchronization measurement."""

    frame_index: int = Field(..., ge=0, description="Zero-based frame sequence index.")
    emitter_timestamp_ms: float = Field(
        ..., ge=0.0, description="Hardware timestamp when screen emitter updated pattern."
    )
    capture_timestamp_ms: float = Field(
        ..., ge=0.0, description="Hardware timestamp when camera registered the frame."
    )
    delta_ms: float = Field(
        ..., description="Delay (capture_timestamp_ms - emitter_timestamp_ms)."
    )
    jitter_ms: Optional[float] = Field(
        default=None, description="Absolute deviation from mean or nominal interval."
    )
    is_dropped: bool = Field(
        default=False, description="Whether this expected frame was dropped."
    )


class JitterTestLog(BaseModel):
    """Complete log for a cross-device synchronization jitter test session."""

    test_id: UUID = Field(..., description="Unique UUID v4 for this test run.")
    device_model: str = Field(..., min_length=1, description="e.g. 'Google Pixel 7', 'Dell XPS 15'")
    device_type: DeviceType = Field(..., description="Device form factor.")
    os_browser: str = Field(..., min_length=1, description="e.g. 'Android 14 / Chrome 126'")
    display_refresh_rate_hz: float = Field(
        ..., gt=0.0, description="Display refresh rate in Hz (e.g. 60.0, 120.0)."
    )
    camera_fps: float = Field(
        ..., gt=0.0, description="Configured camera capture FPS (e.g. 30.0, 60.0)."
    )
    test_timestamp_utc: str = Field(
        ..., description="ISO 8601 UTC timestamp when test was conducted."
    )
    network_condition: NetworkCondition = Field(
        ..., description="Network transmission medium under test."
    )
    nominal_challenge_period_ms: float = Field(
        ..., gt=0.0, description="Target duration of each challenge pattern state."
    )
    samples: List[JitterSampleEntry] = Field(
        ..., min_length=10, description="Array of at least 10 measured frame samples."
    )
    notes: Optional[str] = Field(default=None, description="Optional testing observations.")

    @field_validator("test_timestamp_utc")
    @classmethod
    def validate_utc_timestamp(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(
                f"test_timestamp_utc '{v}' is not a valid ISO 8601 format (e.g. '2026-10-05T14:30:00Z')"
            )
        return v

    @model_validator(mode="after")
    def validate_sample_order(self) -> "JitterTestLog":
        indices = [s.frame_index for s in self.samples]
        if sorted(indices) != list(range(len(indices))):
            raise ValueError("Jitter sample frame_index values must be contiguous starting from 0.")
        return self
