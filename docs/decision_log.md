# Decision Log

All technical decisions must be recorded here. Do NOT log decisions in chat threads or verbal meetings alone.

**Format:** Add entries in reverse-chronological order (newest first).

---

## Template

```
### [YYYY-MM-DD] — <Short decision title>
**Decided by:** M1 / M2 / M3 / Team
**Context:** Why did this decision need to be made?
**Decision:** What was decided?
**Rationale:** Why this option over alternatives?
**Alternatives considered:** What else was on the table?
**Impact:** Which modules / phases does this affect?
```

---

## Log

### [2026-10-04] — Subject identity key and attack session inheritance
**Decided by:** M3 (Aswin)
**Context:** Dataset splitting requires an invariant identity key, but SessionManifest lacked an identity identifier. Furthermore, attack sessions (replays, prints, deepfakes) must not leak into training if generated from a test-set volunteer.
**Decision:** For bona-fide sessions, `subject_id` is set equal to `consent_record_id`, establishing an anonymized, 1-to-1 link without storing personal names. For attack sessions, `source_session_id` is mandatory and references the source session, inheriting the subject identity so partitions remain disjoint.
**Rationale:** Prevents identity leakage across live and spoof splits, preserving auditability for academic publications and patent claims.
**Alternatives considered:** Free-text subject name (rejected — violates privacy SOP); separate identity hashing table (rejected — unnecessary complexity when UUID v4 consent IDs already exist).
**Impact:** `data/schemas.py`, `scripts/preprocess/split_dataset.py`, Phase 2 & 3 evaluations.

### [2026-10-04] — Metric namespace isolation: Synchronization vs Verification Latency
**Decided by:** M3 (Aswin)
**Context:** Hardware-timestamp jitter analysis was initially logging mean transmission delta as `eval/latency_ms`. However, the core ASTCV prototype target requires end-to-end decision latency to be < 150 ms (`eval/latency_ms`).
**Decision:** All frame sync and WebRTC telemetry metrics are strictly namespaced under `sync/*` (e.g. `sync/delta_mean_ms`, `sync/spread_p95_p5_ms`, `sync/drop_rate_pct`). The `eval/latency_ms` key is strictly reserved for the end-to-end capture-to-decision pipeline.
**Rationale:** Eliminates MLflow metric key collisions and ambiguity between transmission delay and algorithmic execution latency.
**Impact:** `eval/tracker.py`, `eval/jitter_analysis.py`, Phase 1 & Phase 3 evaluation harnesses.

### [2026-10-04] — Machine-agnostic DVC configuration and DPDP per-session tracking
**Decided by:** M3 (Aswin)
**Context:** Hardcoding `D:\ASTCV` in Git-tracked `.dvc/config` broke execution on teammates' machines. Additionally, tracking custom volunteer data as a monolithic directory made compliance with India's DPDP Act 2023 right to erasure impossible.
**Decision:** Machine paths are moved to `.dvc/config.local` (ignored by Git). Each custom volunteer session is tracked individually (`data/raw/custom/<session_id>.dvc`). Upon consent withdrawal, the single session pointer is deleted and `dvc gc --force` purges cached objects.
**Rationale:** Ensures repository portability across Windows/Mac/Linux and provides an airtight, audit-ready data erasure workflow.
**Impact:** `.dvc/config`, `docs/data_storage_sop.md`, project compliance.

### [2026-10-04] — Zero-leakage identity-level dataset partitioning policy
**Decided by:** M3 (Aswin)
**Context:** Face and deepfake datasets often contain multiple videos or frames of the same individual. Random frame-level or video-level splits cause severe data leakage and artificially inflate FAR/FRR metrics.
**Decision:** All datasets must be partitioned strictly by actor/subject identity (`scripts/preprocess/split_dataset.py`) with mathematical disjointness verification (`--verify`).
**Rationale:** Preserves scientific credibility for academic publication and patent claims.
**Alternatives considered:** Video-level split (rejected — same actor in train and test corrupts liveness generalization).
**Impact:** `scripts/preprocess/`, `data/manifests/`, Phase 2 & 3 evaluations.

### [2026-10-04] — Repo structure and tooling
**Decided by:** M3 (Aswin)
**Context:** Starting Phase 1 — needed to establish data backbone before sync and calibration work produces storable output.
**Decision:** Role-based folder structure (`data/`, `eval/`, `experiments/`, `scripts/`, `docs/`). Git + DVC for versioning. MLflow for experiment tracking. Portable SSD (`D:\ASTCV`) as primary DVC remote, Google Drive as backup.
**Rationale:** Role-based structure enforces module ownership per the SOP. DVC keeps large data out of git. SSD gives fast local I/O for bulk data operations.
**Alternatives considered:** Phase-based folder structure (rejected — harder to enforce ownership); S3 remote (rejected — no cloud budget confirmed yet).
**Impact:** All phases. Establishes the data backbone.
