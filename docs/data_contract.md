# Data Contract — Screen Emitter ↔ Capture Pipeline

**Owner:** M1 (Amal Krishna J) defines this schema. M3 (Aswin K N) aligns session storage to it.
**Status:** DRAFT — to be finalized by end of Phase 1 (Day 20)
**Last updated:** [DATE]

---

## 1. Session Schema (v1.1.0)

Every captured session must produce one JSON manifest file stored at:
`data/raw/custom/<session_id>/manifest.json`

Validated via: `python -m data.validator data/raw/custom/<session_id>/ --check-frames`

```json
{
  "schema_version": "1.1.0",
  "pipeline_git_commit": "string — commit hash (e.g. '3f13d26')",
  "session_id": "string — UUID v4",
  "subject_id": "string — UUID v4 (equals consent_record_id for LIVE)",
  "source_session_id": "string or null — UUID of source session (MANDATORY for attacks)",
  "device_model": "string — e.g. 'Samsung Galaxy S23', 'Dell XPS 15'",
  "os_browser": "string — e.g. 'Android 14 / Chrome 126'",
  "capture_timestamp_utc": "ISO 8601 string WITH timezone (e.g. '2026-10-05T08:00:00Z')",
  "clock_source": "performance.now | requestVideoFrameCallback | system_monotonic | system_utc",
  "camera_settings": {
    "fps": 30.0,
    "resolution_w": 1280,
    "resolution_h": 720,
    "exposure_locked": true,
    "white_balance_locked": true
  },
  "lighting_condition": "bright_indoor | dim_indoor | natural_outdoor | harsh_side_lit | variable",
  "eyewear": "none | prescription_glasses | sunglasses | tinted_glasses",
  "skin_tone": "optional string (e.g. 'Fitzpatrick_III')",
  "challenge_params": {
    "color_space": "sRGB",
    "intensity_min": 0.1,
    "intensity_max": 0.9,
    "flash_seed": 42
  },
  "challenge_pattern_ids": ["list of strings — ordered sequence of pattern IDs shown"],
  "pattern_events": [
    {
      "pattern_id": "string",
      "emit_timestamp_ms": 0.0,
      "duration_ms": 100.0
    }
  ],
  "frame_timestamp_log": [
    {
      "frame_index": 0,
      "hardware_timestamp_ms": 16.67,
      "pattern_id": "string",
      "is_dropped": false
    }
  ],
  "label": "live | replay | print | virtual_camera | deepfake",
  "consent_flag": true,
  "consent_record_id": "string — UUID v4 linking to docs/consent_records/<id>.pdf",
  "consent_form_version": "v1.1",
  "calibration_applied": true,
  "calibration_version": "v1.0",
  "notes": "optional annotations"
}
```

## 2. Frame Storage

Frames stored as: `data/raw/custom/<session_id>/frames/frame_<NNNNNN>.jpg`
- Zero-padded 6-digit index
- Resolution: native capture resolution, NOT downsampled at ingestion
- Downsampling happens only in `scripts/preprocess/` with logged parameters

## 3. Challenge Pattern Registry

Patterns are defined by M1 and stored at: `data/manifests/challenge_patterns.json`
Each pattern entry:
```json
{
  "pattern_id": "string",
  "type": "string — e.g. 'specular_flash', 'color_sequence'",
  "parameters": {}
}
```

## 4. What M2's Pipeline Must Emit

| Field | Source | Format |
|-------|--------|--------|
| `hardware_timestamp_ms` | Browser `performance.now()` or OS-level | int ms |
| `pattern_id` per frame | Screen emitter log | string |
| Raw frames | WebRTC capture | JPEG, ≥ 720p |
| Device info | User-agent / OS API | string |

## 5. Cross-Device Jitter Benchmark Log Specification

For Phase 1 cross-device synchronization testing (minimum 2 devices: e.g., mobile phone and laptop), M1/M2 must emit a benchmark log stored at:
`data/raw/jitter_tests/<test_id>/jitter_log.json`

Validated via: `data/schemas_jitter.py` (`JitterTestLog`)  
Analyzed via: `python eval/jitter_analysis.py data/raw/jitter_tests/ --log-mlflow`

```json
{
  "test_id": "UUID v4",
  "device_model": "string — e.g. 'Google Pixel 7'",
  "device_type": "mobile | laptop | desktop | tablet",
  "os_browser": "string — e.g. 'Android 14 / Chrome 126'",
  "display_refresh_rate_hz": 60.0,
  "camera_fps": 30.0,
  "test_timestamp_utc": "ISO 8601 UTC string",
  "network_condition": "local | wifi_5ghz | wifi_2.4ghz | cellular_5g | cellular_4g | simulated_jitter",
  "nominal_challenge_period_ms": 50.0,
  "samples": [
    {
      "frame_index": 0,
      "emitter_timestamp_ms": 0.0,
      "capture_timestamp_ms": 48.2,
      "delta_ms": 48.2,
      "jitter_ms": 1.8,
      "is_dropped": false
    }
  ],
  "notes": "optional string"
}
```

## 6. Open Questions (to resolve by Day 10)

- [ ] Clock sync strategy between screen emitter and capture — NTP offset or shared epoch?
- [ ] What is the maximum tolerable jitter before a frame is flagged as unsynced? (Target: < 15ms)
- [ ] Does M2 emit per-frame timestamps or only keyframe timestamps? (Per-frame required for Physicality Score)
