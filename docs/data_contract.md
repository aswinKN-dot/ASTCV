# Data Contract — Screen Emitter ↔ Capture Pipeline

**Owner:** M1 (Amal Krishna J) defines this schema. M3 (Aswin K N) aligns session storage to it.
**Status:** DRAFT — to be finalized by end of Phase 1 (Day 20)
**Last updated:** [DATE]

---

## 1. Session Schema

Every captured session must produce one JSON manifest file stored at:
`data/raw/custom/<session_id>/manifest.json`

```json
{
  "session_id": "string — UUID v4",
  "device_model": "string — e.g. 'Samsung Galaxy S23', 'Dell XPS 15'",
  "os_browser": "string — e.g. 'Android 14 / Chrome 126'",
  "capture_timestamp_utc": "ISO 8601 — session start time in UTC",
  "challenge_pattern_ids": ["list of strings — ordered sequence of pattern IDs shown"],
  "frame_timestamp_log": [
    {
      "frame_index": "int",
      "hardware_timestamp_ms": "int — milliseconds since session start",
      "pattern_id": "string — which challenge pattern was active at this frame"
    }
  ],
  "label": "string — one of: 'live', 'replay', 'print', 'virtual_camera', 'deepfake'",
  "consent_flag": "bool — true only if signed consent record exists for this subject",
  "consent_record_id": "string — UUID linking to consent record in docs/consent_records/",
  "calibration_applied": "bool — whether display-camera calibration was run pre-session",
  "calibration_version": "string or null — e.g. 'v1.2', null if not applied",
  "notes": "string — optional, e.g. 'subject wore glasses', 'low ambient light'"
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

## 5. Open Questions (to resolve by Day 10)

- [ ] Clock sync strategy between screen emitter and capture — NTP offset or shared epoch?
- [ ] What is the maximum tolerable jitter before a frame is flagged as unsynced?
- [ ] Does M2 emit per-frame timestamps or only keyframe timestamps?
