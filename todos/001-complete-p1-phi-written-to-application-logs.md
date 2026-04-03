---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, security, hipaa, phi, logging]
dependencies: []
---

## Problem Statement

PHI (Protected Health Information) is written verbatim to application logs in `patient_data.py`. Three `logger.info` calls emit full clinical content:

- Line 69: `logger.info(f"Loaded patient data for {patient_id}: {response}")` — `response` is the full JSON list of all note metadata (IDs, types, dates)
- Line 149: `logger.info(f"Created timeline for {patient_id}: {response}")` — `response` is the LLM-generated clinical timeline with verbatim clinical content
- Line 217: `logger.info(f"Created answer for {patient_id}: {response}")` — `response` is the LLM-generated Q&A containing patient clinical details

With Azure Monitor connected (configured in `config.py`), this writes PHI to a centralized log store accessible to personnel not authorized to view individual patient records. This is a HIPAA violation.

## Findings

- **File:** `src/scenarios/default/tools/patient_data.py`
- **Lines:** 69, 149, 217
- **Reported by:** security-sentinel
- **Severity:** P1 — CRITICAL HIPAA violation

## Proposed Solutions

### Option A (Recommended): Replace content with safe counters
```python
# Line 69 — replace:
# logger.info(f"Loaded patient data for {patient_id}: {response}")
logger.info("Loaded patient data for patient %s: %d items", patient_id, len(clinical_note_metadatas) + len(image_metadatas))

# Line 149 — replace:
# logger.info(f"Created timeline for {patient_id}: {response}")
logger.info("Created timeline for patient %s", patient_id)

# Line 217 — replace:
# logger.info(f"Created answer for {patient_id}: {response}")
logger.info("Created answer for patient %s", patient_id)
```
- **Pros:** Simple 3-line fix; eliminates PHI from logs entirely; also fixes f-string eager evaluation (lazy % formatting)
- **Cons:** Loses content for debugging (use DEBUG level with appropriate log retention controls if content needed)
- **Effort:** Small
- **Risk:** None

## Recommended Action

Option A — implement immediately.

## Technical Details

- **Affected files:** `src/scenarios/default/tools/patient_data.py` lines 69, 149, 217
- **Root cause:** f-string logger calls with full response content

## Acceptance Criteria

- [ ] No `logger.info/debug/warning/error` call contains `response` variable holding clinical content
- [ ] Log output for patient data load shows item count, not content
- [ ] All three lines updated to use `%s` lazy formatting

## Work Log

- 2026-04-02: Identified by security-sentinel during code review
