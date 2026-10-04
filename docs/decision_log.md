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

### [2026-10-04] — Repo structure and tooling
**Decided by:** M3 (Aswin)
**Context:** Starting Phase 1 — needed to establish data backbone before sync and calibration work produces storable output.
**Decision:** Role-based folder structure (`data/`, `eval/`, `experiments/`, `scripts/`, `docs/`). Git + DVC for versioning. MLflow for experiment tracking. Portable SSD (`D:\ASTCV`) as primary DVC remote, Google Drive as backup.
**Rationale:** Role-based structure enforces module ownership per the SOP. DVC keeps large data out of git. SSD gives fast local I/O for bulk data operations.
**Alternatives considered:** Phase-based folder structure (rejected — harder to enforce ownership); S3 remote (rejected — no cloud budget confirmed yet).
**Impact:** All phases. Establishes the data backbone.
