---
status: pending
priority: p1
issue_id: "148"
tags: [code-review, security, phi, hipaa]
dependencies: []
---

# PHI Exposure in MagenticBot Log Statements

## Problem Statement

`magentic_bot.py:213` logs full message content at INFO level: `logger.info(f"received message: {message}")`. In a tumor board context, these messages contain patient clinical data (diagnoses, staging, treatment history, biomarkers). This creates a PHI exposure vector in application logs forwarded to Azure Monitor / Application Insights.

Line 136 similarly logs `logger.info(f"User input requested: {prompt}")`.

## Findings

- **Source**: Security Sentinel review
- **Evidence**: `src/bots/magentic_bot.py` lines 136 and 213
- **HIPAA Risk**: Application logs are routinely forwarded to Azure Monitor, which may have broader access than the clinical data itself
- **Contrast**: `grounded_clinical_note.py` properly uses `html.escape()` on dynamic values; other routes sanitize logs

## Proposed Solutions

### Option A: Downgrade to DEBUG and strip content (Recommended)
- Change `logger.info(f"received message: {message}")` to `logger.debug("received message from source: %s", getattr(message, 'source', 'unknown'))`
- Change `logger.info(f"User input requested: {prompt}")` to `logger.debug("User input requested (prompt length: %d)", len(prompt))`
- **Pros**: Preserves debug-ability; removes PHI from default log levels
- **Cons**: Slightly harder to debug in production without changing log level
- **Effort**: Small
- **Risk**: Low

### Option B: Log message metadata only
- Log message type, source agent, and character count instead of content
- **Pros**: Retains operational visibility
- **Cons**: Less useful for debugging
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Option A

## Technical Details
- **Affected files**: `src/bots/magentic_bot.py`
- **Lines**: 136, 213

## Acceptance Criteria
- [ ] No patient clinical data appears in INFO-level logs
- [ ] DEBUG-level logs still capture message metadata for troubleshooting
- [ ] Audit all `logger.info` calls in bots/ directory that interpolate message content

## Work Log
- 2026-04-02: Identified during code review (security-sentinel agent)

## Resources
- [HIPAA Logging Requirements](https://www.hhs.gov/hipaa/for-professionals/security/guidance/index.html)
- Related: todos/088-closed-p2-patient-id-in-timeout-warning-logs.md
