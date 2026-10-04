# Data Collection Consent & Ethics Process

**Owner:** M3 (Aswin K N)  
**Faculty Guide & Secondary Custodian:** Leo Francis P  
**Status:** DRAFT v1.1 — Required sign-off from Faculty Guide & Ethics Review before Phase 2 collection  
**Last updated:** 2026-10-04  
**Regulatory Framework:** India's Digital Personal Data Protection (DPDP) Act, 2023 & Institutional Ethics Guidelines

---

## 1. What Is Collected & Biometric Data Classification

**Facial video and image recordings constitute biometric personal data.** Volunteers are informed plainly that the capture pipeline records:
1. **Facial Biometric Video:** Short video stream (≤ 3 minutes) captured via webcam at native resolution.
2. **Hardware Timestamps & Sync Telemetry:** Millisecond-level screen emitter and camera sensor timing logs.
3. **Session Metadata:** Device model, OS, browser version, ambient lighting category, and eyewear presence.
4. **Self-Reported Skin Tone (Optional):** Self-classified using standardized scale (Fitzpatrick I–VI or Monk 1–10) strictly for algorithmic bias auditing across diverse populations.
5. **No Audio:** Microphone access is explicitly disabled in the capture client.

---

## 2. Research Purpose, Intellectual Property & Derived Outputs

- **Purpose:** Academic research on active hardware-timestamped anti-spoofing and liveness verification for the ASTCV project.
- **Patent & Intellectual Property Notice:** The technical methods developed using this dataset will be included in a provisional patent filing and College Intellectual Property Rights (IPR) documentation.
- **Derived Outputs:** Mathematical models, reflectance parameters, and statistical performance curves generated from the data will persist in published academic research and patent disclosures. Raw facial imagery will not be published without separate explicit written release.

---

## 3. Mandatory Health & Photosensitivity Screening

The ASTCV active verification challenge involves screen color and luminance modulation.
- **Exclusion Criteria:** Any individual with a diagnosis of photosensitive epilepsy, history of unprovoked seizures, or adverse reactions to flickering lights/strobe effects is **strictly excluded** from participating.
- **Algorithm Safety Bounds:** M1 (Amal) hardcodes accessibility-safe flashing limits into the emitter algorithm (luminance modulation frequencies kept strictly outside the high-risk 15–25 Hz window, favoring smooth color transitions).

---

## 4. Specific Attack Data Consent Checkboxes

Volunteers must be provided separate, independent consent options on the consent form (`docs/consent_records/consent_form.pdf`):
- [ ] **Core Live Collection:** I consent to video recording of my face during screen challenge patterns.
- [ ] **Replay & Presentation Attack Testing:** I consent to my recorded video being played back on screens or printed onto paper targets to test anti-spoofing defenses.
- [ ] **Virtual Camera & Injection Defense Testing:** I consent to my session data being routed through virtual camera injection software (e.g. OBS Virtual Camera) to evaluate software tamper detection.
- [ ] **Synthetic / Deepfake Generation:** I consent to my facial imagery being used to synthesize benchmark deepfake test samples strictly for evaluating ASTCV detection robustness.
- [ ] **Optional Demographic Annotation:** I voluntarily disclose my self-reported skin tone category for bias measurement.

---

## 5. Age & Eligibility Requirements

- All participants must be **at least 18 years of age**.
- Verification of legal age is mandatory prior to recording. No data from minors will be captured.

---

## 6. Data Storage, Anonymization & Third-Party Privacy

| Data Type | Storage Location | Encryption & Access | Retention |
|---|---|---|---|
| **Raw Session Frames** | `data/raw/custom/<session_id>/` (External SSD `D:\ASTCV`) | DVC-tracked local volume; access restricted to ASTCV team | Project duration + 1 year |
| **Encrypted Cloud Backup** | Google Drive (`gdrive://<folder_id>`) | Encrypted at rest; restricted access | Project duration |
| **Signed Consent PDFs** | `docs/consent_records/<consent_record_id>.pdf` | **Strictly excluded from Git (`.gitignore`)**; encrypted local disk | Project duration + 3 years |
| **Identity Lookup Key** | `docs/identity_map.enc` (outside git) | AES-256 encrypted map linking participant name to UUID | Primary & Secondary Custodians only |

### Third-Party & AI Assistants Policy:
- **STRICT PROHIBITION:** In compliance with DPDP data localization and privacy mandates, **raw volunteer face images or video frames must NEVER be uploaded to public or commercial AI chat assistants** (e.g. ChatGPT, Claude, Gemini, Copilot).
- AI assistants may only inspect schema definitions, anonymized latency numbers, and code.

---

## 7. Data Subject Rights & Consent Withdrawal (DPDP Act 2023)

Under India's Digital Personal Data Protection Act, 2023, participants possess the legal right to withdraw consent and request data erasure:
1. **Right to Withdraw:** A volunteer may withdraw consent at any time prior to the final release freeze (Phase 4, Day 76).
2. **Purge Protocol:** Upon receipt of withdrawal notice:
   - M3 executes the session purge protocol outlined in [`docs/data_storage_sop.md`](file:///C:/Users/Ramdas/OneDrive/Desktop/ASTCV/docs/data_storage_sop.md).
   - The session directory and `.dvc` files are deleted from Git, local cache, and cloud remotes using `dvc gc --force`.
   - The signed consent record is updated with withdrawal timestamp and archived in compliance records.
3. **Post-Freeze Limitation:** Once statistical metrics are permanently aggregated into published papers and patent claims, individual raw data can be deleted from active servers, but aggregated non-biometric statistics cannot be altered.

---

## 8. Data Custodians & Contact

- **Primary Data Custodian:** Aswin K N (M3 - Data Engineer)
- **Secondary Custodian & Faculty Guide:** Leo Francis P
- **Ethics Review Sign-Off Date:** Pending Phase 2 review
