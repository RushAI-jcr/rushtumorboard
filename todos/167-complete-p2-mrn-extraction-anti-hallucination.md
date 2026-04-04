---
status: complete
priority: p2
issue_id: "167"
tags: [code-review, security, agent-native]
dependencies: []
---

# MRN Extraction Fallback Lacks Anti-Hallucination Guard

## Problem Statement

`agents.yaml:76` instructs PatientHistory to use `process_prompt` to extract MRN/name from clinical notes when the demographics CSV is absent. The extraction prompt does NOT include anti-hallucination language ("NEVER fabricate an MRN"). The export prompts have this guard, but the extraction point does not — a hallucinated MRN in a tumor board document could lead to wrong-patient clinical action.

Additionally, the fallback is prompt-only (not codified as a tool), so only PatientHistory can use it. Other agents (PatientStatus, OncologicHistory) cannot independently extract demographics.

## Findings

- **Source**: Security Sentinel (LOW), Agent-Native Reviewer (CRITICAL)
- **File**: `src/scenarios/default/config/agents.yaml`, line 76

## Proposed Solutions

### Option A: Add anti-hallucination guard to prompt (Quick fix)
Add "NEVER guess or fabricate an MRN. If not found, return 'Not found'." to the extraction prompt in agents.yaml.
- **Effort**: Trivial (1 line)

### Option B: Move extraction into load_patient_data code (Better)
If demographics CSV is absent, automatically run an LLM extraction and store result on chat_ctx. All agents benefit.
- **Effort**: Medium
- **Risk**: Low

## Recommended Action

Option A immediately, Option B as follow-up.

## Acceptance Criteria

- [ ] Extraction prompt includes "NEVER fabricate" language
- [ ] Extraction prompt asks for "Not found" when absent

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | Security + Agent-Native reviewers converged on this gap |
