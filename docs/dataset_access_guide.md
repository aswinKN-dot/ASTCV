# Dataset Access & Ingestion Guide

**Owner:** M3 (Aswin K N)  
**Last updated:** 2026-10-04  
**Primary Storage Target:** `D:\ASTCV\data\raw\public\` (Portable SSD)

This guide documents the day-one action checklist for obtaining the 6 benchmark datasets required for ASTCV. Several of these require signed agreements or manual review, which can take multiple business days.

---

## 1. Action Checklist (Submit on Day 1)

| Dataset | Access Type | Action Required | Est. Turnaround | Priority |
|---|---|---|---|---|
| **Celeb-DF v2** | Gated (Email) | Download `Celeb-DF_v2_Request_Form.pdf`, sign with Faculty Guide (Leo Francis P), email to `celebalbany@gmail.com` | 2–5 days | **CRITICAL** |
| **FaceForensics++** | Gated (Form) | Fill out TUM Google Form with academic email (`.edu` / college domain) | 2–4 days | **CRITICAL** |
| **VoxCeleb2** | Gated (Form) | Complete user agreement form on Oxford VGG website | 1–2 days | HIGH |
| **DFDC** | Gated (Kaggle) | Sign in to Kaggle, accept DFDC Competition Rules | Immediate | MEDIUM |
| **UADFV** | Open | Direct download via GitHub repo links | Immediate | IMMEDIATE |
| **FFHQ** | Open | Direct download via NVIDIA GitHub repo scripts | Immediate | MEDIUM |

---

## 2. Detailed Access Instructions

### A. Celeb-DF v2
- **Form:** [Celeb-DF_v2_Request_Form.pdf](https://github.com/yuezunli/celeb-deepfakeforensics/blob/master/Celeb-DF_v2_Request_Form.pdf)
- **Steps:**
  1. Print or digitally sign the request form with:
     - Researcher Name: Aswin K N (M3)
     - Faculty Advisor: Leo Francis P
     - Organization: [College Name]
  2. Send email to `celebalbany@gmail.com` with subject: `[Celeb-DF v2 Request] ASTCV Research Project`.
  3. Once credentials arrive, download to `D:\ASTCV\data\raw\public\celeb_df_v2\`.

### B. FaceForensics++ (FF++)
- **Form:** [TUM Google Form](https://docs.google.com/forms/d/e/1FAIpQLSdRR5UBxewABWuw26pSpde4Oa0fq573C6-l2TqP_u6yY3gq6w/viewform)
- **Steps:**
  1. Submit form using your institutional/college email address.
  2. Wait for email containing the Python download script (`download-FaceForensics.py`) and your access token.
  3. For initial pipeline testing, download the `c23` (light compression) tier first to conserve bandwidth:
     ```bash
     python download-FaceForensics.py D:\ASTCV\data\raw\public\ff++\ -d original -c c23 -t videos
     python download-FaceForensics.py D:\ASTCV\data\raw\public\ff++\ -d Deepfakes -c c23 -t videos
     ```

### C. VoxCeleb2
- **Portal:** [Oxford VGG VoxCeleb2 Registration](https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox2.html)
- **Steps:**
  1. Fill in university affiliation details on the webpage.
  2. Receive HTTP authentication username and password.
  3. Start by downloading the test set (`vox2_test_mp4.zip`, ~9 GB) first.

### D. DFDC (DeepFake Detection Challenge)
- **Portal:** [Kaggle DFDC Dataset](https://www.kaggle.com/c/deepfake-detection-challenge/data)
- **Steps:**
  1. Ensure Kaggle API token is configured (`~/.kaggle/kaggle.json`).
  2. Accept competition rules on the Kaggle website.
  3. Download part 0 first (~10 GB) to verify ingestion pipeline:
     ```bash
     kaggle competitions download -c deepfake-detection-challenge -f dfdc_train_part_0.zip -p D:\ASTCV\data\raw\public\dfdc\
     ```

### E. UADFV
- **Portal:** [GitHub Repo](https://github.com/danmohaha/WIFS2018_In_I_Trust)
- **Steps:**
  1. Download the archive directly from the Google Drive / Box link in the README.
  2. Extract to `D:\ASTCV\data\raw\public\uadfv\`.

### F. FFHQ
- **Portal:** [NVlabs FFHQ Repository](https://github.com/NVlabs/ffhq-dataset)
- **Steps:**
  1. Use the official download script from NVlabs or download the 1024x1024 zip from Google Drive.
  2. Extract to `D:\ASTCV\data\raw\public\ffhq\`.

---

## 3. Strict Identity-Level Split Policy

To guarantee the scientific integrity of ASTCV and prevent data leakage:

1. **Zero Cross-Split Identity Overlap:**
   The exact same identity / actor must NEVER appear in both the training set and the test set.
2. **Pair-Wise Integrity:**
   If a real video of Actor A is used to generate a deepfake video, neither Actor A's real video nor any fake video synthesized from Actor A may appear in test if Actor A is in train.
3. **Partition Manifests:**
   Before any preprocessing or evaluation run, an explicit split manifest must be generated and committed to `data/manifests/<dataset>_splits.json`.
