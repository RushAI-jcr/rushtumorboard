---
status: pending
priority: p3
issue_id: "191"
tags: [code-review, agent-native, prompt-engineering]
dependencies: []
---

# Replace Hardcoded Function Signatures in Orchestrator Prompt

## Problem Statement
The Orchestrator prompt references exact function signatures like `get_pretumor_board_checklist(patient_id, cancer_type)` but the Orchestrator has no tools -- it delegates via natural language. If tool signatures change, the prompt becomes misleading. Should use role-based language instead.

## Findings
- **Source agent:** Agent-Native Reviewer (P2)
- **File:** `src/scenarios/default/config/agents.yaml` (Orchestrator section, line ~10)

## Proposed Solutions
1. Change function-call-style references to role-based delegation language, e.g.:
   - Before: `"run get_pretumor_board_checklist(patient_id, cancer_type)"`
   - After: `"run the pre-meeting checklist"`
   - **Effort:** Small (5 min)

## Acceptance Criteria
- [ ] The Orchestrator prompt no longer contains literal function signatures
- [ ] Delegation instructions use role-based / intent-based language
- [ ] The Orchestrator still correctly delegates the pre-meeting checklist task
- [ ] No other agent prompts are affected
