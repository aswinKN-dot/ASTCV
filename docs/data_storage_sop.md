# Data Storage & DVC Operation SOP

**Owner:** M3 (Aswin K N)  
**Last updated:** 2026-10-04

---

## 1. DVC Remote Configuration Architecture

To ensure cross-platform compatibility across team members:

1. **Shared Repository Config (`.dvc/config`):**
   Committed to Git. Contains only generic remote declarations and placeholder endpoints.
2. **Local Machine Overrides (`.dvc/config.local`):**
   Ignored by Git. Each developer binds the remotes to their specific local drive letters:
   ```bash
   # Windows portable SSD:
   dvc remote modify --local ssd url "D:\ASTCV"

   # Mac/Linux SSD mount:
   dvc remote modify --local ssd url "/Volumes/ASTCV"
   ```

---

## 2. Per-Session Tracking Policy (DPDP Compliance & Data Withdrawal)

> **CRITICAL RULE:** Never track `data/raw/custom/` as a monolithic directory (`dvc add data/raw/custom`).

If the entire custom directory is tracked as a single unit, deleting one volunteer's session changes the hash, but the old historical archive containing their facial biometric data persists forever in DVC cache and remote storage.

### Standard Session Ingestion Procedure:
1. Validate session:
   ```bash
   python -m data.validator data/raw/custom/<session_id>/ --check-frames
   ```
2. Track session individually:
   ```bash
   dvc add data/raw/custom/<session_id>
   git add data/raw/custom/<session_id>.dvc
   git commit -m "data: add verified session <session_id>"
   dvc push -r ssd
   ```

### Volunteer Withdrawal Purge Procedure:
When a volunteer exercises their legal right to consent withdrawal under India's Digital Personal Data Protection (DPDP) Act, 2023:
1. Delete session files and its DVC pointer:
   ```bash
   git rm data/raw/custom/<session_id>.dvc
   rm -rf data/raw/custom/<session_id>
   git commit -m "compliance: purge session <session_id> upon consent withdrawal"
   ```
2. Garbage collect and purge cache locally:
   ```bash
   dvc gc --workspace --force
   ```
3. Purge orphaned objects from external SSD and cloud remotes:
   ```bash
   dvc gc --cloud -r ssd --force
   ```

---

## 3. Public Dataset Redistribution Restrictions

- **Licensing Restriction:** Academic datasets (FaceForensics++, Celeb-DF v2, DFDC, VoxCeleb2) prohibit public hosting or redistribution.
- **Remote Policy:** Do NOT push full public datasets to unauthenticated cloud folders. Store public datasets on local SSD storage (`-r ssd`). Use Google Drive only for internal ASTCV custom sessions and benchmark metrics.
