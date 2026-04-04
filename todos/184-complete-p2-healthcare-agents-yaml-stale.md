---
status: pending
priority: p2
issue_id: "184"
tags: [code-review, agent-native, configuration]
dependencies: []
---

# Remove or deprecate stale healthcare_agents.yaml

## Problem Statement
`healthcare_agents.yaml` contains stale agent overrides that conflict with the canonical `agents.yaml` (e.g., "3-slide" presentation format vs. `agents.yaml`'s standardized "5-slide" for ReportCreation). The config loader currently only loads `agents.yaml`, so `healthcare_agents.yaml` is dead code. However, if it were ever merged or loaded alongside `agents.yaml`, it would silently overwrite the standardized prompts with outdated versions. Several agents in the file have only description fields with no instructions or tools, making them non-functional stubs.

## Findings
- **Source**: Agent-Native Reviewer (P1)
- `src/scenarios/default/config/healthcare_agents.yaml` -- entire file contains stale/conflicting agent definitions

## Proposed Solutions
1. **Delete the file entirely**
   - Remove `healthcare_agents.yaml` from the repository
   - Pros: Eliminates confusion, no risk of accidental loading, clean codebase
   - Cons: Loses historical reference (mitigated by git history)
   - Effort: ~2 minutes

2. **Add a deprecation header and rename**
   - Rename to `healthcare_agents.yaml.deprecated` or add a prominent `# DEPRECATED` header
   - Pros: Preserves the file for reference while signaling it should not be used
   - Cons: Still clutters the config directory, someone could still accidentally load it
   - Effort: ~5 minutes

## Acceptance Criteria
- [ ] `healthcare_agents.yaml` is either deleted or clearly marked as deprecated
- [ ] No code path loads or references `healthcare_agents.yaml`
- [ ] `agents.yaml` remains the single source of truth for agent configuration
- [ ] If deleted, git history preserves the file content for reference
- [ ] All existing tests pass (no test depends on `healthcare_agents.yaml`)
