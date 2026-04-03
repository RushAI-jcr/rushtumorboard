---
status: pending
priority: p3
issue_id: "147"
tags: [code-review, agent-native, reliability]
dependencies: []
---

# 147 — ClinicalTrials agent instructions reference tool names that may not match registered functions

## Problem Statement

The `ClinicalTrials` agent entry in `agents.yaml:437-449` instructs the agent to call four specific MCP tools by name: `search_nci_gyn_trials`, `get_gog_nrg_trials`, `search_aact_trials`, and `get_trial_details_combined`. The agent's `tools:` list references only `clinical_trials` and `clinical_trials_nci`. If the `@kernel_function` names defined in `clinical_trials_nci.py` do not exactly match the names in the instructions, the agent will attempt to call nonexistent functions. Semantic Kernel will silently fail to route the call or the agent will hallucinate trial data rather than surfacing a clear error.

## Findings

- `agents.yaml:437-449` — ClinicalTrials agent `instructions` reference four tool names; `tools:` lists two plugin names
- `src/scenarios/default/tools/clinical_trials_nci.py` — actual `@kernel_function` names need verification against instruction references

## Proposed Solution

1. Audit `clinical_trials_nci.py` to extract all `@kernel_function` decorated method names.
2. Compare each name against the four tool names referenced in the agent's instructions.
3. If names differ, update the instructions to use the exact function names.
4. Add a startup assertion (or unit test) that verifies all tool names cited in agent instructions for every agent exist as registered kernel functions in the loaded kernel:

```python
for agent_cfg in agents:
    for tool_name in agent_cfg.tool_names_from_instructions:
        assert kernel.has_function(tool_name), \
            f"Agent '{agent_cfg.name}' references unknown tool '{tool_name}'"
```

## Acceptance Criteria

- [ ] All tool names in the ClinicalTrials agent instructions are confirmed to match actual `@kernel_function` names in `clinical_trials_nci.py`
- [ ] Any confirmed mismatch is corrected in `agents.yaml` instructions
- [ ] A startup check or unit test verifies instruction-referenced tool names exist as registered kernel functions
- [ ] ClinicalTrials agent does not hallucinate trial data due to unresolvable tool names
