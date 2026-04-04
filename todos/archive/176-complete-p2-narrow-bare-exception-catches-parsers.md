---
status: pending
priority: p2
issue_id: "176"
tags: [code-review, quality, error-handling, phi]
dependencies: ["172"]
---

# Narrow Bare Exception Catches in Selection/Termination Parsers

## Problem Statement

`src/group_chat.py` lines 399 and 409: Both `evaluate_termination` and `evaluate_selection` catch bare `Exception`, swallowing everything from JSON errors to `MemoryError`. Additionally, `logger.warning("... (%s)", exc)` logs the full exception string, which for `ValidationError` includes the raw LLM response that may contain PHI.

## Findings

- **Source**: Python Quality Reviewer (CRITICAL), Security Sentinel (LOW)
- **Evidence**: Lines 399, 409 — `except Exception as exc:`
- **Risk**: Silent swallowing of unexpected errors (AttributeError from SK API changes); PHI in exception strings logged at WARNING

## Proposed Solutions

### Option A: Narrow catch + redact exception string (Recommended)
```python
from pydantic import ValidationError
except (ValidationError, ValueError) as exc:
    logger.warning("Termination parse failed (type=%s), defaulting to continue", type(exc).__name__)
    return False
```
- **Pros**: Only catches expected errors; logs type not content; no PHI exposure
- **Cons**: Unexpected errors will propagate (but this is correct — you want to know about them)
- **Effort**: Small (10 min)
- **Risk**: None

## Acceptance Criteria
- [ ] Exception catches narrowed to (ValidationError, ValueError)
- [ ] Logger outputs only exception type name, not full string
- [ ] Unexpected exceptions propagate normally
