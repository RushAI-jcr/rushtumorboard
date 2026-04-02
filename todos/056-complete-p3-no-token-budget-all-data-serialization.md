---
name: no-token-budget-all-data-serialization
description: content_export.py serializes all_data to JSON with no per-field character caps before sending to GPT-4o
type: code-review
status: pending
priority: p3
issue_id: 056
tags: [code-review, performance, cost, tokens]
---

## Problem Statement

`content_export.py:362-363` serializes the full `all_data` dictionary with `json.dumps(all_data, indent=2, default=str)` and no per-field length caps before sending to Azure OpenAI GPT-4o. High-variability string fields (`medical_history`, `oncologic_history`, `board_discussion`, `ct_scan_findings`) are included without truncation. The new col0 schema grew the prompt approximately 30% with new fields and a schema example. This is likely the highest-cost LLM call in the system, and token count directly increases both latency and cost.

## Findings

`content_export.py:362-363` (approximate):
```python
payload = json.dumps(all_data, indent=2, default=str)
# payload sent directly to Azure OpenAI GPT-4o
```

High-variability fields with no length constraints before serialization:
- `medical_history`
- `oncologic_history`
- `board_discussion`
- `ct_scan_findings`

These fields can contain multi-paragraph free-text clinical notes. A single field could contain thousands of tokens. No truncation, summarization, or length cap is applied before the JSON is assembled.

The col0 schema change added new fields and a schema example to the same prompt, compounding the growth.

## Proposed Solutions

### Option A
Add `_MAX_FIELD_CHARS` module-level constants and truncate high-variability fields before `json.dumps`.

```python
_MAX_ONCOLOGIC_HISTORY_CHARS = 4000
_MAX_MEDICAL_HISTORY_CHARS = 2000
_MAX_BOARD_DISCUSSION_CHARS = 3000
_MAX_CT_FINDINGS_CHARS = 3000

# Before json.dumps:
all_data["oncologic_history"] = (all_data.get("oncologic_history") or "")[:_MAX_ONCOLOGIC_HISTORY_CHARS]
all_data["medical_history"] = (all_data.get("medical_history") or "")[:_MAX_MEDICAL_HISTORY_CHARS]
all_data["board_discussion"] = (all_data.get("board_discussion") or "")[:_MAX_BOARD_DISCUSSION_CHARS]
all_data["ct_scan_findings"] = (all_data.get("ct_scan_findings") or "")[:_MAX_CT_FINDINGS_CHARS]
```

**Pros:** Predictable token ceiling; reduces cost and latency; constants are easily tunable; avoids truncation surprises by using named constants.
**Cons:** Hard truncation may cut important clinical text; requires calibration of limits against actual data; LLM output quality may degrade for edge-case long notes.
**Effort:** Small
**Risk:** Low (truncation thresholds can be set conservatively high to start)

### Option B
Accept current behavior; monitor token usage via Azure OpenAI metrics and revisit if cost exceeds threshold.

**Pros:** No code change; no truncation risk.
**Cons:** Cost and latency remain unbounded; no visibility without active monitoring setup.
**Effort:** Small (monitoring setup only)
**Risk:** Low (financial risk, not correctness risk)

## Technical Details

**Affected files:**
- `content_export.py` (lines 362-363 and surrounding `all_data` assembly block)

**Related context:**
- The col0 schema was introduced in the branch under review; this finding is a consequence of that growth.
- Azure OpenAI GPT-4o pricing is per token (input + output); this call is the primary cost driver per patient export.

## Acceptance Criteria

- [ ] Either: per-field character caps are applied to at least the 4 high-variability fields before `json.dumps`, with named constants at module level
- [ ] Or: a monitoring/alerting mechanism is documented that will trigger review if per-call token count exceeds a defined threshold
- [ ] No regression in export content quality for typical-length clinical notes
- [ ] Truncation (if implemented) does not silently truncate mid-sentence without an indicator (e.g., appending `"... [truncated]"`)

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
