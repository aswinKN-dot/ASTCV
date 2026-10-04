# ASTCV — Anti-Spoofing via Temporal-Calibrated Vision

> **Hardware-agnostic liveness detection** using display-camera calibration, hardware-timestamp synchronization, and adaptive-challenge mechanics.

## Team

| Role | Member | Ownership |
|------|--------|-----------|
| M1 — ML & Physics Modeler | Amal Krishna J | `models/`, `docs/data_contract.md` |
| M2 — CV Engineer & Demo Builder | Abhijith Krishna P S | `pipeline/`, `ui/` |
| M3 — Data Engineer | Aswin K N | `data/`, `eval/`, `scripts/` |
| Faculty Guide | Leo Francis P | Project oversight |

## Repository Structure

```
ASTCV/
├── data/
│   ├── raw/
│   │   ├── public/          # Gated datasets (DVC-tracked, not in git)
│   │   └── custom/          # Volunteer webcam sessions (DVC-tracked)
│   ├── processed/           # Extracted frames, crops, splits (DVC-tracked)
│   └── manifests/           # Dataset cards, session manifest JSONs
├── eval/
│   ├── metrics.py           # FAR, FRR, latency
│   ├── visualize.py         # ROC/DET curves, ablation tables
│   └── harness.py           # Single-command evaluation runner
├── experiments/
│   └── mlruns/              # MLflow store (DVC-tracked)
├── scripts/
│   └── preprocess/          # Frame extraction, face crop, split scripts
└── docs/
    ├── data_contract.md     # Schema M1/M2 must emit
    ├── consent_process.md   # Data collection consent SOP
    └── decision_log.md      # All technical decisions — no chat threads
```

## DVC Remotes

| Remote | Path | Role |
|--------|------|------|
| `ssd` (default) | `D:\ASTCV` | Primary — portable SSD |
| `gdrive` | TBD | Backup — Google Drive |

## Quick Start

```bash
# Clone repo
git clone <repo-url>
cd ASTCV

# Pull data from SSD (must be connected)
dvc pull -r ssd

# Run evaluation harness
python eval/harness.py --model <version> --data <dataset>
```

## MLflow

```bash
# Start MLflow UI
mlflow ui --backend-store-uri experiments/mlruns
# Open http://localhost:5000
```

## Naming Conventions

- **Experiments:** `phase{N}_{description}` e.g. `phase1_sync_baseline`
- **Runs:** `{device}_{dataset}_{date}` e.g. `pixel7_ff++_20261005`
- **Dataset versions:** Tag in DVC — `v1.0`, `v1.1`, etc.

## SOPs

- Weekly 30-min sync: status and blockers only
- All decisions → `docs/decision_log.md` (not chat threads)
- Module ownership enforced via folder structure above
- Hardware validation: test on ≥ 2–3 distinct phone/laptop models
- No data collected without signed consent
