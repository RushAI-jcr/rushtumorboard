---
status: pending
priority: p1
issue_id: "225"
tags: [code-review, security, hipaa]
dependencies: []
---

# MRN Logged in Plaintext at INFO Level (HIPAA)

## Problem Statement

`caboodle_file_accessor.py` logs MRN values at INFO level during MRN-to-GUID resolution. MRNs are direct patient identifiers — logging them in plaintext violates HIPAA minimum-necessary and creates PHI exposure in Azure Application Insights.

## Findings

**Flagged by:** Security Sentinel (HIGH), Performance Oracle, Architecture Strategist

**File:** `src/data_models/epic/caboodle_file_accessor.py`

In `resolve_patient_id()`:
```python
logger.info("Resolved MRN %s → patient folder %s", identifier, patient_id)
logger.info("MRN %s not found in index; returning as-is", identifier)
```

In `_build_mrn_index_sync()`:
```python
logger.info("Built MRN index: %d entries from %d patient folders", len(index), folders_scanned)
```

The first two log MRN values directly. The third is safe (counts only).

## Proposed Solutions

### Option A: Mask MRN + reduce to DEBUG (Recommended)
```python
logger.debug("Resolved MRN ***%s -> patient folder %s", identifier[-4:], patient_id)
logger.debug("MRN ***%s not found in index; returning as-is", identifier[-4:])
```
- Shows last 4 digits for debugging without exposing full MRN
- DEBUG level prevents production log ingestion (Azure Monitor filters INFO+)
- Effort: Small | Risk: None

### Option B: Remove MRN from log entirely
```python
logger.debug("Resolved MRN -> patient folder %s", patient_id)
logger.debug("MRN not found in index; returning identifier as-is")
```
- Effort: Small | Risk: Slightly harder to debug

## Acceptance Criteria

- [ ] No full MRN values appear in any log message
- [ ] Log level reduced to DEBUG for MRN resolution messages
- [ ] MRN masked to last 4 digits if included at all

## Work Log

- 2026-04-09: Created from Phase 2 code review — flagged by Security Sentinel, confirmed by 3 other agents
