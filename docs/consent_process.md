# Data Collection Consent Process

**Owner:** M3 (Aswin K N)
**Status:** DRAFT — must be signed off before ANY volunteer collection begins (Phase 2)
**Last updated:** [DATE]

---

## 1. What Is Collected

- Short video session (≤ 5 minutes) captured via webcam
- Metadata: device model, OS/browser, timestamp, ambient lighting condition
- No audio is recorded
- No biometric identifiers beyond facial appearance are stored

## 2. Purpose

Data is used exclusively for academic research on liveness detection for the ASTCV project under [College Name]. It will not be shared with third parties or used for commercial purposes.

## 3. Consent Procedure

1. Volunteer reads the **Participant Information Sheet** (attach as `docs/consent_records/participant_info_sheet.pdf`)
2. Volunteer completes the **Consent Form** (attach as `docs/consent_records/consent_form.pdf`) — digital signature acceptable
3. M3 assigns a `consent_record_id` (UUID v4) and stores the signed form at `docs/consent_records/<consent_record_id>.pdf`
4. Session is only captured after step 3 is complete — `consent_flag: true` is only set when a valid `consent_record_id` exists

## 4. Data Storage and Retention

| Item | Storage | Retention |
|------|---------|-----------|
| Raw session frames | `data/raw/custom/` (DVC-tracked, SSD) | Duration of project + 1 year |
| Session manifest | `data/raw/custom/<session_id>/manifest.json` | Same |
| Consent form | `docs/consent_records/` (git-tracked, private) | Duration of project + 3 years |
| Processed frames | `data/processed/` (DVC-tracked) | Duration of project |

> **Note:** Consent records directory must NOT be pushed to any public remote. Keep it in a private repo or encrypted local store.

## 5. Anonymization

- Sessions are identified by UUID only — no name stored in the dataset
- Name-to-UUID mapping kept separately in a password-protected local file, accessible only to M3
- Any visualizations or paper figures must not show identifiable faces without explicit additional consent

## 6. Right to Withdraw

- Any participant may withdraw at any time before the dataset freeze (Phase 4, Day 76)
- On withdrawal: session files are deleted from all remotes, and the consent record is updated with withdrawal date
- After dataset freeze, withdrawal is not possible due to irreversibility of aggregated results

## 7. Collection Protocol Checklist

Before each session:
- [ ] Signed consent form on file
- [ ] Calibration target in place (Abhijith's printed target)
- [ ] Capture pipeline version logged
- [ ] Device model and OS recorded
- [ ] Lighting condition noted (bright indoor / dim indoor / outdoor)
- [ ] Glasses / no glasses noted
- [ ] Skin tone diversity tracked across the volunteer pool

## 8. IPR and Compliance

- College IPR sign-off must be obtained before any data is published or shared externally
- Follow all institutional ethics board requirements for human subjects data

## 9. Open Items

- [ ] Get ethics board / IRB sign-off from [College Name] — required before Phase 2 collection starts
- [ ] Finalize Participant Information Sheet with Faculty Guide (Leo Francis P)
- [ ] Confirm retention policy with college data protection officer
