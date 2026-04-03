---
name: patient-id-in-telemetry-log-content-export
description: Full patient_id (PHI) is logged at INFO level in content_export.py and presentation_export.py, shipping it to Azure Application Insights on every export
type: code-review
status: complete
priority: p2
issue_id: 051
tags: [code-review, phi, security, hipaa, logging]
---

## Problem Statement

`content_export.py:198`: `logger.info(f"Generating tumor board doc for patient {patient_id}")` — `patient_id` logged at INFO level with an f-string. Azure Monitor telemetry is configured in `config.py` with `logging_exporter_enabled=True`. This ships `patient_id` (a PHI identifier) to Application Insights on every Word doc generation. The same pattern exists in `presentation_export.py:183`. The PHI log issue was previously addressed (todo 001) for other callers but not for these export tools.

## Findings

- `content_export.py:198`: `logger.info(f"Generating tumor board doc for patient {patient_id}")` — full GUID logged
- `presentation_export.py:183`: same pattern — full `patient_id` at INFO level
- `config.py`: `logging_exporter_enabled=True` — all INFO logs are shipped to Azure Application Insights
- `patient_id` is a PHI identifier (Epic patient GUID) — logging it violates HIPAA minimum necessary standard
- This pattern was identified and fixed for other callers in todo 001, but the export plugins were not included in that fix
- Both files use f-string interpolation, which embeds the full value unconditionally regardless of log level filtering

## Proposed Solutions

### Option A
Replace both log statements with a truncated prefix: `logger.info("Generating tumor board doc for patient %s...", patient_id[:8])` — logs only the first 8 characters of the GUID, which is non-identifying but sufficient for correlation/debugging.

**Pros:** Consistent with the fix pattern from todo 001; non-identifying prefix is sufficient for log correlation; uses `%s` formatting (lazy interpolation, not f-string)
**Cons:** First 8 chars of a GUID are not unique across a large patient population
**Effort:** Trivial (< 15 minutes)
**Risk:** None

### Option B
Hash the `patient_id` before logging: `logger.info("Generating tumor board doc for patient %s", hashlib.sha256(patient_id.encode()).hexdigest()[:12])`. The hash is a consistent pseudonymous identifier that supports log correlation without exposing the raw GUID.

**Pros:** Pseudonymous identifier supports log correlation without PHI exposure; consistent hash means the same patient always produces the same log token
**Cons:** Adds `import hashlib`; slightly more verbose; hash is not human-readable
**Effort:** Trivial (< 15 minutes)
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/plugins/content_export.py` (line 198)
- `src/plugins/presentation_export.py` (line 183)

## Acceptance Criteria

- [ ] `content_export.py:198` does not log the full `patient_id`
- [ ] `presentation_export.py:183` does not log the full `patient_id`
- [ ] Both log statements use `%s` lazy formatting (not f-string)
- [ ] Fix is consistent with the pattern established in todo 001
- [ ] No other INFO/DEBUG log statements in either file contain `patient_id` as a raw value

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
