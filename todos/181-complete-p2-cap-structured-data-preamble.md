---
status: pending
priority: p2
issue_id: "181"
tags: [code-review, performance, llm]
dependencies: []
---

# Cap structured data preamble size in oncologic history extractor

## Problem Statement
`oncologic_history_extractor.py` serializes diagnoses, staging, and medications as `json.dumps(indent=2)` into the LLM prompt preamble. With extensive medication lists, the structured preamble can consume 25-40KB of the 120KB token budget, crowding out the clinical notes that contain the actual oncologic history. No independent cap exists for the preamble portion, so a patient with many medications gets a disproportionately worse extraction because notes are truncated to fit.

## Findings
- **Source**: Performance Oracle (Priority 1)
- `src/scenarios/default/tools/oncologic_history_extractor.py:192-201` -- structured data serialized with `json.dumps(indent=2)` with no size cap

## Proposed Solutions
1. **Add MAX_STRUCTURED_CHARS constant and compact JSON**
   - Define `MAX_STRUCTURED_CHARS = 30_000` at module level
   - Switch from `json.dumps(indent=2)` to `json.dumps(separators=(',', ':'))` (compact format)
   - If the combined preamble exceeds the cap, truncate medications first (they are typically the largest and least critical for extraction)
   - Pros: Predictable budget allocation, preserves clinical notes space, simple to implement
   - Cons: Truncated medications may occasionally miss relevant data
   - Effort: ~30 minutes

2. **Filter medications to oncology-relevant before serialization**
   - Filter by OrderClass (chemotherapy, targeted, immunotherapy, hormone therapy) before serializing
   - Combine with compact JSON for maximum space savings
   - Pros: Removes noise, improves extraction quality AND reduces size
   - Cons: Requires understanding medication OrderClass values; needs fallback if no oncology meds found
   - Effort: ~1 hour (overlaps with issue #186)

## Acceptance Criteria
- [ ] A `MAX_STRUCTURED_CHARS` constant (or equivalent) caps the preamble size
- [ ] JSON serialization uses compact format (no `indent=2`)
- [ ] When preamble exceeds the cap, medications are truncated first with a note indicating truncation
- [ ] Clinical notes receive at least 60% of the total token budget
- [ ] Extraction quality is unchanged or improved on test cases with extensive medication lists
- [ ] All existing tests pass
