---
status: pending
priority: p1
issue_id: "103"
tags: [code-review, performance, async, clinical-trials]
dependencies: []
---

# 103 — `search_clinical_trials` Blocks Entire Workflow with Sequential LLM Loop

## Problem Statement

`search_clinical_trials` in `src/scenarios/default/tools/clinical_trials.py:156-169` fetches up to 50 trials (`pageSize=50`) from ClinicalTrials.gov, then evaluates each trial with a separate sequential `await` to the LLM inside a `for` loop. With a 90–150 second per-call timeout, this design can block the entire tumor board workflow for up to 75 minutes (50 × 90s). There is no `asyncio.gather`, no concurrency cap via semaphore, and no per-trial timeout. This is the most likely root cause of ClinicalTrials agent timeouts observed in production.

Three additional issues in the same file:
- A dead code alias `response_results = chat_completion_responses` at line 171 is assigned but the variable used immediately thereafter is named differently.
- A nested-quote f-string at line 155 (`f"Clinical trials found: {len(result["studies"])}"`) is a SyntaxError in Python 3.12+ (and a latent bug in earlier versions).

## Findings

- `clinical_trials.py:156-169` — `for study in studies: ... response = await kernel.invoke(...)` — fully sequential `await` inside for-loop with no timeout wrapper per iteration.
- `pageSize=50` in the ClinicalTrials.gov query parameters — 50 sequential LLM calls at worst case.
- Line 171: `response_results = chat_completion_responses` — `response_results` is never referenced again; `chat_completion_responses` is used directly. Dead alias.
- Line 155: `f"Clinical trials found: {len(result["studies"])}"` — nested double-quotes inside an f-string. SyntaxError in Python 3.14; undefined behavior in 3.11/3.12.

## Proposed Solution

1. **Replace sequential for-loop with `asyncio.gather` behind a semaphore:**

   ```python
   _SEM = asyncio.Semaphore(5)
   _TRIAL_TIMEOUT = 45  # seconds

   async def _evaluate_trial(kernel, study):
       async with _SEM:
           return await asyncio.wait_for(
               kernel.invoke(..., study=study),
               timeout=_TRIAL_TIMEOUT
           )

   results = await asyncio.gather(
       *[_evaluate_trial(kernel, s) for s in studies],
       return_exceptions=True
   )
   ```

   `return_exceptions=True` ensures one failed trial does not cancel all others.

2. **Reduce `pageSize` from 50 to 10–15.** The LLM already re-ranks and filters; fetching 50 for downstream filtering is wasteful and the primary driver of worst-case latency.

3. **Remove the dead `response_results` alias** at line 171.

4. **Fix the nested-quote f-string** at line 155:

   ```python
   study_count = len(result["studies"])
   logger.info(f"Clinical trials found: {study_count}")
   ```

## Acceptance Criteria

- [ ] `search_clinical_trials` uses `asyncio.gather` with `return_exceptions=True` (not a sequential for-loop)
- [ ] Concurrent LLM calls limited to ≤5 simultaneous via `asyncio.Semaphore`
- [ ] Each per-trial LLM call is wrapped in `asyncio.wait_for` with an explicit timeout ≤60s
- [ ] `pageSize` reduced from 50 to ≤15 in the ClinicalTrials.gov query
- [ ] Nested-quote f-string at line 155 replaced with a safe alternative (no SyntaxError)
- [ ] Dead `response_results = chat_completion_responses` alias removed
- [ ] A test verifies that a 10-trial result set completes within the per-trial timeout × concurrency cap (not 10 × timeout sequentially)
