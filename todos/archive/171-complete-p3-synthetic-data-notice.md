---
status: complete
priority: p3
issue_id: "171"
tags: [code-review, security, hipaa, documentation]
dependencies: []
---

# Add SYNTHETIC_DATA_NOTICE to infra/patient_data/

## Problem Statement

`infra/patient_data/patient_gyn_cerv_001/` and `patient_gyn_gtn_001/` contain realistic clinical data including HIV serology results (for the cervical patient) and hCG trajectories (for the GTN patient). A reviewer unfamiliar with the project could confuse these for real patient data. The CLAUDE.md states "All patient data in infra/patient_data/ is synthetic" but this notice is not present in the directory itself.

**Why:** Defense-in-depth documentation. If a future developer sees an HIV result in the CSV, they should immediately see that all data is synthetic. This also protects against accidental real-patient data being committed alongside these synthetic files.

## Proposed Solution

Add `infra/patient_data/SYNTHETIC_DATA_NOTICE.md`:

```markdown
# Synthetic Patient Data Notice

All patient data in this directory is **entirely synthetic and fictitious**.

No real patient identifiers, dates, or clinical data are present. All names,
patient IDs, dates, diagnoses, lab results, and clinical notes were
artificially generated for testing purposes only.

Real patient data (UUID-named folders) is gitignored and not tracked.
```

**Effort:** Trivial.

## Acceptance Criteria

- [ ] `infra/patient_data/SYNTHETIC_DATA_NOTICE.md` exists and is committed
- [ ] Contents clearly state all data is synthetic

## Work Log

- 2026-04-03: Identified by security-sentinel during code review
