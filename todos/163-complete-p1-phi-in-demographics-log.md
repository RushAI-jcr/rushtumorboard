---
status: complete
priority: p1
issue_id: "163"
tags: [code-review, security, hipaa]
dependencies: []
---

# PHI in Demographics Log Statement

## Problem Statement

`patient_data.py:120-123` logs patient MRN and full name at INFO level via `logger.info("Loaded demographics for patient %s: MRN=%s, Name=%s", ...)`. In production, all INFO-level logs are piped through OpenTelemetry to Azure Application Insights (`config.py:23-54`). This means real patient MRN and full name (both HIPAA identifiers) are stored in a cloud-hosted log store that is not designated as a HIPAA-compliant PHI repository.

Every other logger call in this codebase carefully logs only `patient_id` (a GUID), never direct identifiers. This call breaks that pattern.

## Findings

- **Source**: Security Sentinel (CRITICAL), Python Reviewer (MEDIUM), Architecture Strategist (noted)
- **File**: `src/scenarios/default/tools/patient_data.py`, lines 120-123
- **Evidence**: `logger.info("Loaded demographics for patient %s: MRN=%s, Name=%s", patient_id, demographics.get("MRN", "N/A"), demographics.get("PatientName", "N/A"))`

## Proposed Solutions

### Option A: Remove PHI from log (Recommended)
- Change to: `logger.info("Loaded demographics for patient %s", patient_id)`
- **Pros**: Simplest, zero PHI exposure risk
- **Cons**: Less diagnostic info
- **Effort**: Trivial (1 line)
- **Risk**: None

### Option B: Mask PHI values
- Log masked values: `MRN=****39, Name=J***`
- **Pros**: Some diagnostic value retained
- **Cons**: Still partial PHI exposure, more complex
- **Effort**: Small
- **Risk**: Low

### Option C: Downgrade to DEBUG
- Change `logger.info` to `logger.debug`
- **Pros**: Not emitted in production (DEBUG typically disabled)
- **Cons**: Still present if DEBUG is enabled
- **Effort**: Trivial
- **Risk**: Low

## Recommended Action

Option A — remove PHI entirely from the log statement.

## Technical Details

- **Affected files**: `src/scenarios/default/tools/patient_data.py`
- **Components**: PatientDataPlugin.load_patient_data()

## Acceptance Criteria

- [ ] MRN and PatientName are NOT present in any INFO or WARNING level log statement
- [ ] Demographics loading is still confirmed by a log message (without PHI)
- [ ] Grep codebase for other instances of MRN/PatientName in logger calls

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | All 3 security-focused reviewers flagged this |

## Resources

- HIPAA Safe Harbor: 18 identifiers that constitute PHI
- Past solution: `docs/solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md` — mentions UUID-only logging pattern
