---
status: complete
priority: p2
issue_id: "167"
tags: [code-review, performance, agents, token-budget]
dependencies: []
---

# MedicalResearch Agent Missing max_completion_tokens Override

## Problem Statement

ClinicalGuidelines, ReportCreation, and ClinicalTrials now have `max_completion_tokens: 8192`. MedicalResearch does not, falling back to the group_chat.py default of 4096. MedicalResearch produces RISEN synthesis outputs (structured abstract + multi-paper citations) that rival ClinicalGuidelines in length — especially for cervical or GTN cases requiring KEYNOTE-826, GOG-240, EMA-CO, or EMA-EP literature.

**Why:** An asymmetric token budget means MedicalResearch responses get truncated at 4096 while ClinicalGuidelines gets 8192 for similar output complexity. Truncated RISEN synthesis produces incomplete literature summaries that may omit critical trial data from the tumor board packet.

**How to apply:** Add `max_completion_tokens: 8192` to the MedicalResearch agent block in agents.yaml.

## Findings

**Source:** architecture-strategist + agent-native-reviewer

**Location:** `src/scenarios/default/config/agents.yaml` — MedicalResearch agent block (search "name: MedicalResearch")

**Current state:**
```yaml
- name: MedicalResearch
  # ... no max_completion_tokens key
  # Falls through to group_chat.py line 193:
  # max_completion_tokens = agent_config.get("max_completion_tokens", 4096)
```

**Agents already at 8192:** ClinicalGuidelines, ReportCreation, ClinicalTrials

## Proposed Solutions

### Option A: Add max_completion_tokens: 8192 to MedicalResearch (Recommended)

```yaml
- name: MedicalResearch
  max_completion_tokens: 8192
  instructions: |
    ...
```

- **Pros:** Consistent with peer agents that produce long structured outputs
- **Effort:** Trivial (1 line)
- **Risk:** Marginally higher Azure OpenAI cost; acceptable given medical accuracy requirement

### Option B: Leave at 4096 and add token budget instruction to agent prompt
Instruct MedicalResearch to "limit RISEN synthesis to 3000 tokens."
- **Cons:** LLMs don't reliably count tokens; truncation is unpredictable

## Recommended Action

_(Leave blank — fill during triage)_

## Technical Details

- **Affected file:** `src/scenarios/default/config/agents.yaml`
- **Pattern:** Same as existing `max_completion_tokens: 8192` additions at lines 404, 440, 528

## Acceptance Criteria

- [ ] MedicalResearch agent block has `max_completion_tokens: 8192`
- [ ] All 4 content-producing agents (ClinicalGuidelines, ReportCreation, ClinicalTrials, MedicalResearch) now have explicit token budgets

## Work Log

- 2026-04-03: Identified by architecture-strategist + agent-native-reviewer during code review
