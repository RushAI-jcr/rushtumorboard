---
status: complete
priority: p2
issue_id: "021"
tags: [code-review, agents-yaml, maintainability, orchestration]
dependencies: []
---

## Problem Statement

The pre-meeting procedure pass (Step 0) instruction is duplicated in `agents.yaml`: it appears in both the **Orchestrator** agent instructions and the **PatientStatus** agent instructions. This means:

1. The orchestration logic for when/how to call `get_pretumor_board_checklist` is defined in two places
2. If the step 0 behavior changes (e.g., new required items, changed trigger condition), it must be updated in both agents
3. It's unclear which agent "owns" Step 0 — Orchestrator delegates to PatientStatus but both describe the same logic

## Findings

- **File:** `src/scenarios/default/config/agents.yaml` — Orchestrator section (step 0 delegation) and PatientStatus section (step 0 execution)
- **Reported by:** architecture-strategist, code-simplicity-reviewer
- **Severity:** P2 — maintenance burden; confusing ownership

## Proposed Solutions

### Option A (Recommended): Keep execution in PatientStatus, simplify Orchestrator delegation
Orchestrator should say "Step 0: ask PatientStatus to run the pre-meeting checklist." PatientStatus owns the detailed logic of what that entails. Remove the duplicated description from Orchestrator.
```yaml
# Orchestrator — simplified:
# Step 0: Direct PatientStatus to run get_pretumor_board_checklist for the patient before starting case review.

# PatientStatus — owns full logic:
# Run get_pretumor_board_checklist(patient_id) to verify all pre-meeting requirements...
```
- **Pros:** Clear ownership; one place to update; follows existing pattern where Orchestrator delegates, agents own their domain
- **Cons:** None
- **Effort:** Small (edit agents.yaml)
- **Risk:** None (agents.yaml changes are prompt-only; no code change)

### Option B: Keep both but reference PatientStatus from Orchestrator
Make Orchestrator explicitly say "delegate Step 0 to PatientStatus per its instructions" — making the delegation explicit rather than duplicating the content.
- **Effort:** Tiny
- **Risk:** None

## Recommended Action

Option A — remove the step 0 implementation details from Orchestrator, keep only the delegation instruction.

## Technical Details

- **Affected file:** `src/scenarios/default/config/agents.yaml`
- **Sections:** Orchestrator agent instructions (step 0 block), PatientStatus agent instructions (step 0 block)

## Acceptance Criteria

- [ ] Pre-meeting checklist logic described in exactly one agent's instructions (PatientStatus)
- [ ] Orchestrator's step 0 is a one-line delegation: "direct PatientStatus to run pre-meeting checklist"
- [ ] No behavior change — agents still run the checklist before case review

## Work Log

- 2026-04-02: Identified by architecture-strategist and code-simplicity-reviewer during code review
- 2026-04-02: Already resolved — Orchestrator step 0 is already a 2-line delegation to PatientStatus. PatientStatus owns the full execution logic (lines 294-297 of agents.yaml).
