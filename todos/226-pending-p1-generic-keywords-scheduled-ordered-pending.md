---
status: pending
priority: p1
issue_id: "226"
tags: [code-review, performance, radiology]
dependencies: []
---

# Generic Keywords "scheduled"/"ordered"/"pending" Defeat Layer 3 Filtering

## Problem Statement

The words "scheduled", "ordered", and "pending" were added to `layer3_keywords` in radiology_extractor.py to catch pending imaging studies. However, these words appear in virtually every clinical note (medication orders, lab orders, appointment scheduling) and will cause Layer 3 to match ~90%+ of notes — effectively disabling the keyword filter. This is the exact anti-pattern that was previously corrected (docs/solutions/ records that generic keywords caused 81% match rate).

## Findings

**Flagged by:** ALL 7 review agents (unanimous consensus)
- Security Sentinel: MEDIUM (over-extraction, token waste)
- Performance Oracle: Priority 1 (defeats selectivity)
- Architecture Strategist: HIGH (architectural regression)
- Kieran Python Reviewer: HIGH (repeats known anti-pattern)
- Code Simplicity Reviewer: YAGNI violation
- Agent-Native Reviewer: WARNING (breadth concern)
- Learnings Researcher: Confirmed prior incident — generic keywords were deliberately narrowed

**File:** `src/scenarios/default/tools/radiology_extractor.py` — `layer3_keywords` tuple

```python
# Pending/scheduled imaging keywords
"scheduled", "ordered", "pending",
```

These standalone words will substring-match any note containing "labs ordered", "appointment scheduled", "results pending", etc.

## Proposed Solutions

### Option A: Compound phrases only (Recommended)
Replace standalone words with imaging-specific compound phrases:
```python
# Pending imaging — compound phrases only (standalone words match everything)
"imaging scheduled", "imaging ordered", "imaging pending",
"scan scheduled", "scan ordered", "scan pending",
"study scheduled", "study ordered", "study pending",
"mri scheduled", "mri ordered", "ct scheduled", "ct ordered",
"pet scheduled", "pet ordered", "us scheduled", "us ordered",
```
- Effort: Small | Risk: None — LLM prompt rules 12-13 still guide extraction

### Option B: Remove entirely, rely on LLM prompt
The system prompt already has rules 12-13 telling the LLM to look for pending imaging. Layer 3 keywords don't need to catch pending studies — the notes will already be selected by other imaging keywords (CT, MRI, PET, etc.).
- Effort: Tiny | Risk: Minimal — pending imaging mentioned alongside a modality keyword will still be caught

## Recommended Action

Option B is simplest and aligns with YAGNI. If a note mentions "MRI pelvis ordered", it's already caught by "mri". The only case Option A helps is a note that says "imaging scheduled" with no modality name — rare and low-value.

## Acceptance Criteria

- [ ] "scheduled", "ordered", "pending" removed as standalone keywords
- [ ] Either replaced with compound phrases (Option A) or removed entirely (Option B)
- [ ] Layer 3 match rate stays below 30% on representative patient data

## Work Log

- 2026-04-09: Created from Phase 2 code review — unanimous consensus across all 7 agents
