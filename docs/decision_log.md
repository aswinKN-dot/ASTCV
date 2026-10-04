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

### [2026-10-04] — Cross-device jitter benchmark schema & MLflow integration
**Decided by:** M3 (Aswin)
**Context:** Phase 1 requires cross-device jitter testing across minimum 2 hardware devices (e.g. phone vs laptop). A formal storage and analysis contract was needed so M1/M2 test outputs are immediately verifiable.
**Decision:** Standardized jitter test schema (`data/schemas_jitter.py`) storing JSON logs in `data/raw/jitter_tests/<test_id>/jitter_log.json`. Created analysis runner (`eval/jitter_analysis.py`) tracking mean latency, std dev, P95/P99 latency, and frame drop rates logged to MLflow experiment `phase1_jitter_benchmark`.
**Rationale:** Enforces quantitative validation of synchronization bounds before physical reflectance modeling begins in Phase 2.
**Alternatives considered:** Ad-hoc CSV logs (rejected — lack schema validation and metadata tracking).
**Impact:** `data/`, `eval/`, Phase 1 synchronization deliverables.

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
