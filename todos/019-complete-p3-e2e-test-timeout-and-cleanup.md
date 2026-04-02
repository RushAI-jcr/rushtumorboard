---
name: TestClinicalGuidelinesE2E missing timeout and shared kernel fixture
description: E2E test can hang indefinitely on slow Azure OpenAI calls; kernel setup is duplicated from TestAzureOpenAI
type: quality
status: complete
priority: p3
issue_id: "019"
tags: [testing, code-quality, code-review]
---

## Problem Statement

`TestClinicalGuidelinesE2E.test_agent_cites_nccn_pages` has two issues:

**1. No timeout on `agent.invoke()`**
The async iteration `async for msg in agent.invoke(patient_summary)` can hang indefinitely if Azure OpenAI is slow, rate-limited, or has a transient error. Without a timeout, the test suite blocks CI/CD until the 6-hour GitHub Actions default job timeout.

**2. Kernel build duplicated from TestAzureOpenAI**
The ~20-line block that builds `AzureChatCompletion`-backed `Kernel` with API key vs. `AzureCliCredential` branching is copy-pasted verbatim from `TestAzureOpenAI` (lines ~300-328). There's already a `@pytest.fixture(scope="session")` pattern used for `caboodle` and `data_access`. A shared `azure_kernel` fixture would eliminate duplication.

**Affected file:** `src/tests/test_local_agents.py`

## Proposed Solution

**Timeout fix:**
```python
import asyncio

# In the test:
async for msg in asyncio.wait_for(
    agent.invoke(patient_summary).__aiter__(),
    timeout=120.0
):
    response_text += str(msg.content) if msg.content else ""
```

Or use `pytest-timeout`:
```python
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_agent_cites_nccn_pages(self):
```

**Kernel fixture:**
Extract to a session-scoped fixture in `conftest.py` or at the top of `test_local_agents.py`:
```python
@pytest.fixture(scope="session")
def azure_kernel():
    """Shared AzureChatCompletion kernel for E2E tests."""
    ...  # shared build logic
    return kernel
```

**Effort:** Small (timeout: 3 lines; fixture: extract ~20 lines)

## Acceptance Criteria
- [ ] E2E test has an explicit timeout ≤ 120 seconds
- [ ] CI/CD will not hang if Azure OpenAI is unavailable
- [ ] (Optional) Kernel build logic is not duplicated across test classes

## Work Log
- 2026-04-02: Identified by kieran-python-reviewer and code-simplicity-reviewer during code review of the new TestClinicalGuidelinesE2E class.
- 2026-04-02: Implemented and marked complete.
