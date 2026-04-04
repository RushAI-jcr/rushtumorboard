---
name: bare-except-swallows-parse-errors-export-tools
description: Export tools catch all exceptions without logging the error object — schema drift failures are undebuggable in production
type: code-review
status: complete
priority: p1
issue_id: 039
tags: [code-review, reliability, logging, debugging]
---

## Problem Statement
Both export tools catch all exceptions without logging the error object: `content_export.py:378` and `presentation_export.py:252` use `except Exception:` with only a generic warning message. The actual `ValidationError` or `json.JSONDecodeError` is silently discarded. In production, when the LLM drifts from the schema (a common occurrence after model updates), operators see only "using fallback" with zero indication of which field failed or what the LLM returned. Debugging these failures requires reproducing the exact LLM output.

## Findings
- `src/scenarios/default/tools/content_export/content_export.py:378`: `except Exception: logger.warning("LLM response did not match TumorBoardDocContent schema, using fallback")` — exception object not bound or logged.
- `src/scenarios/default/tools/presentation_export.py:252`: Same bare `except Exception:` pattern with same generic message and no exception details.

## Proposed Solutions
### Option A
Bind and log the exception in both locations: `except Exception as exc: logger.warning("LLM response did not match schema, using fallback: %s", exc, exc_info=True)`.

**Pros:** One-line change per site; surfaces exception type, message, and traceback in Application Insights; zero behavior change for end users
**Cons:** None
**Effort:** Small
**Risk:** Low

### Option B
Additionally log the first 500 characters of the raw LLM response at DEBUG level for diagnostics.

**Pros:** Provides full context for reproducing schema drift failures without needing to rerun; makes model-update regressions immediately identifiable
**Cons:** Raw LLM response may contain PHI fragments if the model echoes input — must ensure DEBUG level is not forwarded to external log sinks
**Effort:** Small
**Risk:** Low (if DEBUG log forwarding is audited)

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/scenarios/default/tools/content_export/content_export.py:378`
- `src/scenarios/default/tools/presentation_export.py:252`

## Acceptance Criteria
- [ ] Both except blocks bind the exception with `as exc`
- [ ] Both log `exc` and `exc_info=True` so Application Insights captures the full traceback
- [ ] If Option B: DEBUG log of raw LLM response is reviewed for PHI exposure risk before enabling
- [ ] A test that injects an invalid LLM response confirms the warning log contains the exception message

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
