---
status: pending
priority: p2
issue_id: "179"
tags: [code-review, architecture, agent-orchestration]
dependencies: []
---

# Selection Prompt Lacks Agent Dependency Ordering and Turn Tracking

## Problem Statement

`src/group_chat.py` lines 312-338: The selection prompt only has generic rules ("agents may talk among themselves", "default to facilitator"). It does not encode the dependency graph between agents. Combined with `target_count=12` history truncation, the selection LLM cannot verify which agents have already spoken, causing potential re-delegation or skipped agents.

## Findings

- **Source**: Agent-Native Reviewer (Critical #2, #3)
- **Evidence**: Lines 312-338 — selection prompt template; line 426 — `target_count=12`
- **Risk**: ClinicalGuidelines may run before PatientStatus provides staging; ReportCreation may run before all data agents complete
- **Clinical Impact**: Incomplete tumor board presentations missing critical agent contributions

## Proposed Solutions

### Option A: Add explicit dependency section to selection prompt (Recommended)
Add after the "General Rules" section:
```
3. **Agent Dependencies** (respect these ordering constraints):
   - PatientHistory must run before Pathology, Radiology, OncologicHistory
   - PatientStatus depends on PatientHistory and Pathology
   - ClinicalGuidelines depends on PatientStatus
   - ClinicalTrials depends on PatientStatus
   - MedicalResearch depends on ClinicalGuidelines
   - ReportCreation runs LAST after all other agents
```
- **Pros**: Low-cost change (~10 lines); high impact on orchestration reliability
- **Cons**: Makes the prompt longer
- **Effort**: Small (15 min)
- **Risk**: Low

### Option B: Add turn-tracking metadata
Inject "Agents who have already spoken this turn: [list]" before {{$history}}
- **Pros**: Prevents re-delegation even after history truncation
- **Cons**: Requires tracking agent names in a set per turn
- **Effort**: Medium (45 min)
- **Risk**: Low

## Acceptance Criteria
- [ ] Selection prompt includes agent dependency ordering
- [ ] Agent ordering in 10-agent tumor board follows clinical workflow
