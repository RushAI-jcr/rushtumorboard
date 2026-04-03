---
status: closed
priority: p2
issue_id: "087"
tags: [code-review, security, hipaa]
dependencies: []
---

# P2 — Pydantic ValidationError with `exc_info=True` can echo PHI field values into logs

## Problem Statement

In both `_summarize_for_slides` and `_summarize_for_tumor_board_doc`, an `except Exception` block uses `exc_info=True`. Pydantic `ValidationError` messages routinely echo the offending field value (e.g., `input_value='Martinez, Elena — ...'`). This PHI-containing exception message flows into Azure Monitor via the root logger.

## Findings

**`presentation_export.py`, line 321:**
```python
except Exception as exc:
    logger.warning("LLM response did not match SlideContent schema, using fallback: %s", exc, exc_info=True)
```

**`content_export.py`, line 426:**
```python
except Exception as exc:
    logger.warning("LLM response did not match TumorBoardDocContent schema, using fallback: %s", exc, exc_info=True)
```

Example Pydantic ValidationError that would appear in logs:
```
1 validation error for SlideContent
patient_title
  Value error, unexpected token 'Martinez, Elena' ... [input_value='Martinez, Elena — Case 1 — IIIC']
```

## Proposed Solution

Log only the exception type; preserve full details in a separate debug-level log without PHI exposure:

```python
except Exception as exc:
    logger.warning(
        "LLM response did not match SlideContent schema (type=%s), using fallback",
        type(exc).__name__,
    )
```

## Acceptance Criteria
- [ ] `exc_info=True` removed from both schema-mismatch warning calls
- [ ] Only `type(exc).__name__` logged at WARNING level (not the exception message itself)
- [ ] Same fix applied in `content_export.py`
