---
status: pending
priority: p1
issue_id: "172"
tags: [code-review, security, phi, hipaa, performance]
dependencies: []
---

# PHI Leakage in CustomHistoryChannel Diagnostic Logging

## Problem Statement

`src/group_chat.py` lines 125-135: The `invoke()` override logs the first 80 characters of message content at `logger.info` level via `content=%.80s`. In a tumor board system, message content contains patient diagnoses, staging, biomarkers, and treatment history. Application Insights is configured with `logging_exporter_enabled=True` (config.py:49), so every agent invocation dumps up to 5 messages of patient data into Azure Monitor.

Additionally, lines 395/404 log full `result` objects at DEBUG which may contain PHI in the LLM's reasoning about patient data.

## Findings

- **Source**: Security Sentinel, Performance Oracle, Code Simplicity Reviewer (all flagged independently)
- **Evidence**: `src/group_chat.py` lines 125-135 (invoke override), lines 395/404 (parser debug logs)
- **HIPAA Risk**: PHI in application logs violates the Minimum Necessary Rule. Azure Monitor is not a HIPAA-designated clinical data store.
- **Performance**: INFO-level logging in the hottest path (every agent turn) creates allocation pressure and Azure Monitor I/O overhead
- **Simplicity**: The entire invoke() override is pure diagnostic scaffolding with zero functional purpose (delegates fully to super().invoke())

## Proposed Solutions

### Option A: Delete invoke() override entirely (Recommended)
- Remove lines 117-137 completely. Zero behavioral change.
- For parser logs, log only `type(exc).__name__` not the full exception string
- **Pros**: -21 LOC, eliminates PHI risk, removes per-turn overhead, simplest fix
- **Cons**: Loses thread-state visibility (can re-add gated behind DEBUG if needed later)
- **Effort**: Small (15 min)
- **Risk**: None — the method only logs and delegates to super()

### Option B: Downgrade to DEBUG with isEnabledFor guard
- Change logger.info to logger.debug, wrap in `if logger.isEnabledFor(logging.DEBUG)`
- Remove `content=%.80s` from the format string — log only structural metadata
- **Pros**: Preserves diagnostic capability when DEBUG is enabled
- **Cons**: PHI still reachable if someone enables DEBUG in production
- **Effort**: Small (10 min)
- **Risk**: Low

## Acceptance Criteria
- [ ] No patient content logged at INFO or WARNING level in group_chat.py
- [ ] Exception handlers log only exception type, not full string
- [ ] Azure Monitor log search for "DIAG" returns zero new hits after deploy
