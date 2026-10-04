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

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ClockDomain(str, Enum):
    """Synchronization clock domain."""
    SAME_DEVICE_SHARED_CLOCK = "same_device_shared_clock"
    CROSS_DEVICE_NTP_SYNC = "cross_device_ntp_sync"
    CROSS_DEVICE_UNSYNCED = "cross_device_unsynced"


class JitterSampleEntry(BaseModel):
    """Per-frame synchronization measurement."""
    model_config = ConfigDict(extra="forbid")

    frame_index: int = Field(..., ge=0, description="Zero-based frame sequence index.")
    emitter_timestamp_ms: float = Field(
        ..., ge=0.0, description="Hardware timestamp when screen emitter updated pattern."
    )
    capture_timestamp_ms: Optional[float] = Field(
        default=None, ge=0.0, description="Hardware timestamp when camera registered frame (None if dropped)."
    )
    delta_ms: Optional[float] = Field(
        default=None, description="Measured delay (capture_timestamp_ms - emitter_timestamp_ms)."
    )
    jitter_ms: Optional[float] = Field(
        default=None, description="Absolute deviation from nominal interval."
    )
    is_dropped: bool = Field(
        default=False, description="Whether this expected frame was dropped."
    )


class JitterTestLog(BaseModel):
    """Complete log for a cross-device synchronization jitter test session."""
    model_config = ConfigDict(extra="forbid")

    test_id: UUID = Field(..., description="Unique UUID v4 for this test run.")
    device_model: str = Field(..., min_length=1, description="e.g. 'Google Pixel 7', 'Dell XPS 15'")
    device_type: DeviceType = Field(..., description="Device form factor.")
    os_browser: str = Field(..., min_length=1, description="e.g. 'Android 14 / Chrome 126'")
    clock_domain: ClockDomain = Field(
        default=ClockDomain.SAME_DEVICE_SHARED_CLOCK,
        description="Clock domain architecture (same physical clock vs NTP synchronized)."
    )
    display_refresh_rate_hz: float = Field(
        ..., gt=0.0, description="Display refresh rate in Hz (e.g. 60.0, 120.0)."
    )
    camera_fps: float = Field(
        ..., gt=0.0, description="Configured camera capture FPS (e.g. 30.0, 60.0)."
    )
    test_timestamp_utc: str = Field(
        ..., description="Timezone-aware ISO 8601 UTC timestamp when test was conducted."
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
        try:
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Timestamp must include an explicit timezone offset or 'Z'.")
        except Exception as e:
            raise ValueError(
                f"test_timestamp_utc '{v}' is not a valid timezone-aware ISO 8601 format: {e}"
            )
        return v

    @model_validator(mode="after")
    def validate_sample_order_and_deltas(self) -> "JitterTestLog":
        indices = [s.frame_index for s in self.samples]
        if sorted(indices) != list(range(len(indices))):
            raise ValueError("Jitter sample frame_index values must be contiguous starting from 0.")

        for s in self.samples:
            if s.is_dropped:
                # When dropped, capture_timestamp_ms and delta_ms should be None
                if s.capture_timestamp_ms is not None or s.delta_ms is not None:
                    raise ValueError(
                        f"Frame {s.frame_index} is marked is_dropped=True but has capture_timestamp_ms or delta_ms set."
                    )
            else:
                # When not dropped, capture_timestamp_ms and delta_ms are required
                if s.capture_timestamp_ms is None or s.delta_ms is None:
                    raise ValueError(
                        f"Frame {s.frame_index} is not dropped but missing capture_timestamp_ms or delta_ms."
                    )
                # Mathematical consistency check
                expected_delta = s.capture_timestamp_ms - s.emitter_timestamp_ms
                if abs(expected_delta - s.delta_ms) > 0.5:
                    raise ValueError(
                        f"delta_ms inconsistent at frame {s.frame_index}: "
                        f"recorded {s.delta_ms}ms != expected {expected_delta:.2f}ms"
                    )
                if self.clock_domain == ClockDomain.SAME_DEVICE_SHARED_CLOCK and s.delta_ms < 0:
                    raise ValueError(
                        f"Capture occurred before emit (delta_ms = {s.delta_ms} < 0) at frame {s.frame_index} "
                        f"under shared clock domain."
                    )
        return self
