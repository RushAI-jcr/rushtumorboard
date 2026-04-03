---
status: pending
priority: p1
issue_id: "108"
tags: [code-review, reliability, python]
dependencies: []
---

# 108 — Overly Broad `except` in `_save_research_papers` Swallows All Errors

## Problem Statement

`_save_research_papers` in `medical_research.py:668` uses `except (ResourceNotFoundError, Exception)`. Because `ResourceNotFoundError` is a subclass of `Exception`, the second clause is a strict superset of the first — this is functionally identical to a bare `except Exception:`. Any write-permission error, JSON corruption, network failure, or programming mistake in the blob read path is silently caught and discarded: `research_papers = papers` runs instead, overwriting previously accumulated citations without any log entry at ERROR level or above. The subsequent blob `write` call has no try/except at all — if it fails (after a successful read fallback), the exception propagates all the way up through `process_prompt` as an unhandled error, surfacing to the user as a generic crash rather than a recoverable storage warning.

The secondary issue — `medical_research.py:174` logging external API failures at WARNING when INFO is the appropriate level for anticipated operational conditions — contributes to log noise that buries genuine warnings.

## Findings

- `medical_research.py:665-673` — `try: ... except (ResourceNotFoundError, Exception): research_papers = papers`. The `Exception` clause makes the `ResourceNotFoundError` clause redundant. Any exception type, including `PermissionError`, `ValueError`, `AttributeError`, is silently swallowed.
- The fallback behavior (`research_papers = papers`) discards all previously persisted citations. If the blob was readable but the parse step failed (e.g., corrupt JSON), this silently resets the citation store.
- The blob `write` call that follows the except block has no error handling. A transient storage failure at write time raises an unhandled exception from inside a `@kernel_function`.
- `medical_research.py:174` — external source failure (e.g., PubMed timeout, ClinicalTrials.gov 429) logged at WARNING. These are expected transient conditions in clinical environments with rate-limited APIs; WARNING implies an actionable problem for an operator.

## Proposed Solution

1. **Replace the broad except with specific, intended types:**

   ```python
   try:
       raw = await blob_accessor.read(key)
       existing = json.loads(raw)
       research_papers = existing + papers
   except ResourceNotFoundError:
       # Blob does not exist yet — first write for this patient
       research_papers = papers
   except json.JSONDecodeError as exc:
       logger.warning("_save_research_papers: corrupt blob content, resetting: %s", exc)
       research_papers = papers
   except Exception:
       logger.exception("_save_research_papers: unexpected error reading blob; re-raising")
       raise
   ```

2. **Wrap the blob `write` call:**

   ```python
   try:
       await blob_accessor.write(key, json.dumps(research_papers))
   except Exception:
       logger.warning("_save_research_papers: failed to persist research papers to blob", exc_info=True)
       # Non-fatal: the papers are still returned to the caller for the current session
   ```

3. **Downgrade external API failure logs** at line 174 from `logger.warning` to `logger.info`.

## Acceptance Criteria

- [ ] `except (ResourceNotFoundError, Exception)` replaced; `Exception` is no longer caught silently
- [ ] `json.JSONDecodeError` is caught explicitly with a logged warning
- [ ] Any unexpected exception from the blob read path is logged at ERROR level and re-raised
- [ ] The blob `write` call is wrapped in a try/except that logs a warning on failure without crashing the function
- [ ] External API failure log at line 174 changed from `logger.warning` to `logger.info`
- [ ] A test verifies that a `PermissionError` during blob read propagates (not silently swallowed)
