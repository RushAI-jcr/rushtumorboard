---
status: complete
priority: p2
issue_id: "131"
tags: [code-review, reliability, performance]
dependencies: []
---

# 131 — Blob upload retry loop catches all exceptions, uses fixed 1s delay with no jitter

## Problem Statement

The blob upload retry loops in both export tools use `except Exception` and `asyncio.sleep(1.0)` — a fixed 1-second delay with no jitter and no backoff. This catches and retries permanent failures (`PermissionError`, `ResourceNotFoundError`, `InvalidURL`) that will never succeed, wasting 1 second per attempt and producing a misleading `STORAGE_FAILED` error after retries are exhausted rather than a more descriptive permanent-failure message. Under concurrent load, all callers hitting the same transient Azure Storage throttle will retry at the same time (synchronized retries), amplifying the throttle rather than distributing it.

## Findings

- `presentation_export.py:281-292` — retry loop; `except Exception`; `asyncio.sleep(1.0)` fixed delay
- `content_export.py:257-269` — same pattern; `except Exception`; `asyncio.sleep(1.0)` fixed delay

## Proposed Solution

1. Distinguish retryable exceptions from permanent ones:
   - Retryable: HTTP 429, 503, `azure.core.exceptions.ServiceRequestError`, transient network errors
   - Permanent (do not retry): `PermissionError`, `ResourceNotFoundError`, `InvalidURL`, HTTP 403, HTTP 404

2. On permanent errors, raise immediately with a descriptive message; do not consume retry budget.

3. Replace the fixed sleep with exponential backoff and jitter:

```python
import random
delay = random.uniform(0.5, 1.5) * (2 ** attempt)
await asyncio.sleep(delay)
```

4. Consider raising the retry cap from 2 to 3 attempts for retryable errors.

## Acceptance Criteria

- [ ] `PermissionError`, `ResourceNotFoundError`, and `InvalidURL` are not retried; they fail immediately with a descriptive error
- [ ] Retryable errors (429, 503, `ServiceRequestError`) still use the retry loop
- [ ] Retry delay uses exponential backoff with random jitter on both export tools
- [ ] Fixed `asyncio.sleep(1.0)` calls removed from both retry loops
- [ ] Both loops updated consistently (no drift between `presentation_export.py` and `content_export.py`)
