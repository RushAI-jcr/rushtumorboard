---
status: complete
priority: p3
issue_id: "010"
tags: [code-review, security, hipaa, phi, gitignore]
dependencies: []
---

## Problem Statement

The `.gitignore` pattern `infra/patient_data/[A-F0-9]*-*-*-*-*/` only matches uppercase hex GUIDs. UUID RFC 4122 does not mandate case — Linux tools (`uuidgen`), Python's `uuid.uuid4()`, some Epic environments, and Azure SDK outputs produce lowercase GUIDs (`a05cde0b-...` style). A real patient folder created with a lowercase GUID would not be matched and would be tracked by git.

## Findings

- **File:** `.gitignore` line 27
- **Reported by:** security-sentinel
- **Severity:** P3 — potential PHI in git if lowercase GUIDs exist

## Proposed Solutions

### Option A: Add lowercase pattern
```gitignore
infra/patient_data/[A-F0-9]*-*-*-*-*/
infra/patient_data/[a-f0-9]*-*-*-*-*/
```

### Option B (Recommended): Allowlist approach — exclude all, explicitly include synthetic patients
```gitignore
# Exclude all patient data by default (PHI protection)
infra/patient_data/*/
# Re-include only known synthetic test patients
!infra/patient_data/patient_gyn_001/
!infra/patient_data/patient_gyn_002/
!infra/patient_data/patient_4/
```
Safer for HIPAA: any new directory is excluded by default unless explicitly whitelisted.

- **Effort:** Trivial
- **Risk:** None

## Recommended Action

Option B — allowlist is safer; any future real patient folder is protected automatically.

## Acceptance Criteria

- [ ] A lowercase GUID folder (e.g., `a05cde0b-1234-5678-abcd-ef0123456789/`) is gitignored
- [ ] `patient_gyn_001`, `patient_gyn_002`, `patient_4` are tracked normally
- [ ] `git status` confirms no new patient folders appear as untracked

## Work Log

- 2026-04-02: Identified by security-sentinel
