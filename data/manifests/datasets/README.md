# Dataset Cards — `data/manifests/datasets/`

One YAML card per dataset. These are the **authoritative reference** for:
- Where to request access (do this on Day 1)
- License and usage restrictions
- Exact storage paths in `data/raw/public/`
- Identity-level split rules (to prevent data leakage)
- Role in ASTCV evaluation

## Card Files

| File | Dataset | Access Type | Size |
|------|---------|-------------|------|
| `ff++.yaml` | FaceForensics++ | Gated (form) | ~1.5 TB |
| `celeb_df_v2.yaml` | Celeb-DF v2 | Gated (email) | ~2.1 GB |
| `dfdc.yaml` | DFDC | Gated (Kaggle) | ~470 GB |
| `uadfv.yaml` | UADFV | Open | ~1.1 GB |
| `ffhq.yaml` | FFHQ | Open (ToS) | ~90 GB |
| `voxceleb2.yaml` | VoxCeleb2 | Gated (form) | ~145 GB |

## YAML Card Schema

```yaml
name:               # Full dataset name
short_name:         # Identifier used in code and run names
version:            # Dataset version string
source_url:         # Official GitHub / website
access_type:        # open | gated_form | gated_email | gated_kaggle
access_url:         # Where to submit the access request
access_notes:       # What info is required, typical wait time
license:            # License name
license_restrictions: # Key usage restrictions in plain language
approx_size_gb:     # Approximate download size in GB
n_real:             # Number of real videos/images
n_fake:             # Number of fake videos/images
manipulation_types: # List of forgery types (for deepfake datasets)
official_splits:    # Whether official train/val/test splits exist
split_strategy:     # How to split — MUST be identity-level
known_biases:       # Known demographic/technical biases to document
astcv_role:         # How this dataset is used in ASTCV evaluation
storage_path:       # Expected path under data/raw/public/
status:             # pending_access | downloaded | preprocessed
notes:              # Any other relevant notes
```

> **Rule:** Never split by video/image — always split by **identity (subject ID)**
> so the same person never appears in both train and test sets.
