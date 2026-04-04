---
status: pending
priority: p2
issue_id: "186"
tags: [code-review, performance, clinical]
dependencies: []
---

# Filter medications to oncology-relevant before LLM prompt serialization

## Problem Statement
In `oncologic_history_extractor.py`, ALL medications (including supportive care, antiemetics, pain management, and unrelated prescriptions) are serialized into the LLM prompt. This introduces noise that dilutes the model's attention on clinically relevant oncologic treatments, wastes token budget, and can degrade extraction quality. A patient with 50+ active medications (common in oncology) may have only 5-10 that are oncology-relevant.

## Findings
- **Source**: Performance Oracle (Priority 2)
- `src/scenarios/default/tools/oncologic_history_extractor.py:176` -- all medications serialized without filtering

## Proposed Solutions
1. **Filter by medication OrderClass before serialization**
   - Filter medications to oncology-relevant classes: chemotherapy, targeted therapy, immunotherapy, hormone therapy
   - Include a fallback: if no oncology medications match, include all medications (to handle edge cases where OrderClass is missing or unexpected)
   - Pros: Reduces noise, improves extraction quality, saves token budget (potentially 10-30KB)
   - Cons: Requires knowing the OrderClass values used in the data; risk of excluding relevant medications if OrderClass is miscategorized
   - Effort: ~45 minutes

2. **Use a curated oncology medication list**
   - Maintain a list of known oncology drug names and filter medications by name matching
   - Pros: Independent of OrderClass data quality
   - Cons: Maintenance burden, may miss new drugs, more complex matching logic
   - Effort: ~2 hours

## Acceptance Criteria
- [ ] Medications are filtered to oncology-relevant OrderClass values before serialization
- [ ] Fallback to all medications if no oncology medications match the filter
- [ ] Filtered medication count is logged for observability
- [ ] Token budget savings are measurable (at least 30% reduction in medication section size for patients with extensive medication lists)
- [ ] Extraction quality is unchanged or improved on test cases
- [ ] All existing tests pass
