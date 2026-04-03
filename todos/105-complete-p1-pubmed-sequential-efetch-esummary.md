---
status: complete
priority: p1
issue_id: "105"
tags: [code-review, performance, async, medical-research]
dependencies: []
---

# 105 — PubMed EFetch and ESummary Issued Sequentially Despite No Data Dependency

## Problem Statement

In `medical_research.py:297-300`, the EFetch and ESummary requests to PubMed are issued as two sequential `await` calls. Both requests depend only on the PMID list established before either call — neither result is an input to the other. Running them sequentially doubles the latency of the PubMed retrieval step without any benefit. At NCBI's unauthenticated rate limit of 3 requests/second, this also reduces available capacity for subsequent searches within the same session.

## Findings

- `medical_research.py:283-302` — sequential pattern:
  1. `async with session.get(PUBMED_EFETCH_URL, params={..., "id": pmid_list}) as efetch_resp:` (await)
  2. `async with session.get(PUBMED_ESUMMARY_URL, params={..., "id": pmid_list}) as esummary_resp:` (await after efetch completes)
- Both requests use the identical `pmid_list` constructed at line 283. There is no data flowing from the EFetch response into the ESummary query or vice versa.
- The PubMed API permits up to 3 unauthenticated requests/second (10/second with API key). Issuing both calls concurrently halves the wall-clock wait time and stays within rate limits.

## Proposed Solution

Replace the sequential `async with session.get(...)` pattern with `asyncio.gather` on the two coroutines:

```python
async def _fetch(session, url, params):
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.text()

efetch_text, esummary_text = await asyncio.gather(
    _fetch(session, PUBMED_EFETCH_URL, {**base_params, "id": pmid_list}),
    _fetch(session, PUBMED_ESUMMARY_URL, {**base_params, "id": pmid_list}),
)
```

Update result handling to unpack both values from the gather tuple and process them as before. No change to downstream parsing logic is required — only the awaiting pattern changes.

If NCBI rate limiting becomes a concern (e.g., other concurrent PubMed calls elsewhere), wrap the gather in the existing rate-limit semaphore or add `asyncio.wait_for` with a per-request timeout matching the value used elsewhere in the file.

## Acceptance Criteria

- [ ] EFetch and ESummary requests are issued concurrently via `asyncio.gather` (not sequential `await`)
- [ ] Result handling updated to unpack the gather tuple into `efetch_text` and `esummary_text` (or equivalent names)
- [ ] No functional change to downstream XML/JSON parsing of either response
- [ ] A test verifies that both HTTP requests are initiated before either response is consumed (e.g., by mocking the session and asserting both calls were made before either `.text()` completes)
