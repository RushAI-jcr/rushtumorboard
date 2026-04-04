---
status: pending
priority: p1
issue_id: "172"
tags: [code-review, python, architecture, bug]
dependencies: []
---

# OncologicHistory._extract() Missing LLM Timeout

## Problem Statement

`OncologicHistoryExtractorPlugin._extract()` in `src/scenarios/default/tools/oncologic_history_extractor.py` overrides the base class `_extract()` but does NOT include the `asyncio.wait_for()` timeout wrapper that the base class applies at `medical_report_extractor.py`. If the Azure OpenAI call hangs, this request blocks indefinitely. The base class uses `_LLM_TIMEOUT_SECS = 90.0`.

## Findings

- **Source**: Architecture Strategist (Priority 1 BUG)
- **File**: `src/scenarios/default/tools/oncologic_history_extractor.py:244` — the `chat_completion_service.get_chat_message_contents()` call has no timeout wrapper
- **Comparison**: Base class at `src/scenarios/default/tools/medical_report_extractor.py` uses `asyncio.wait_for(..., timeout=self._LLM_TIMEOUT_SECS)`

## Proposed Solutions

### Option A: Add asyncio.wait_for wrapper (Recommended)
Wrap the LLM call at line 244 with `asyncio.wait_for()` using the same `_LLM_TIMEOUT_SECS` constant from the base class.

- **Pros**: Quick fix, consistent with base class pattern
- **Cons**: Still has duplicated LLM logic (see future refactor todo)
- **Effort**: Small (5 min)

### Option B: Extract shared _call_llm_and_parse() method from base class
Move the LLM call + JSON fence parsing + timeout into a reusable protected method on MedicalReportExtractorBase. OncologicHistory calls it instead of duplicating.

- **Pros**: Eliminates ~35 lines of duplication, prevents this bug class from recurring
- **Cons**: Larger refactor, touches base class contract
- **Effort**: Medium (30-60 min)

## Acceptance Criteria

- [ ] OncologicHistory._extract() LLM call has asyncio.wait_for with 90s timeout
- [ ] TimeoutError is caught and returns a graceful error JSON (not a crash)
- [ ] Existing tests still pass
