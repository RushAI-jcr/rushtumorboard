---
name: 3slide-5slide-docstring-agents-yaml-coherence
description: Stale "3-slide" references in presentation_export.py docstring and agents.yaml conflict with the correct 5-slide schema
type: code-review
status: complete
priority: p2
issue_id: 044
tags: [code-review, documentation, agents-yaml, coherence]
---

## Problem Statement

`presentation_export.py:118` docstring says "Generate a 3-slide PPTX tumor board summary" — stale since the schema now has 5 slides. `agents.yaml` line 385 also describes the PPTX as a "3-slide presentation summary". The `@kernel_function` description at line 99 correctly says "5-slide". Semantic Kernel exposes the `@kernel_function` description to the LLM orchestrator; the stale `agents.yaml` description will cause the ReportCreation agent to communicate incorrect slide count to users.

## Findings

- `presentation_export.py:118`: method docstring reads "Generate a 3-slide PPTX tumor board summary" (stale)
- `agents.yaml:385`: describes the PPTX export as a "3-slide presentation summary" (stale)
- `presentation_export.py:99`: `@kernel_function` description correctly says "5-slide" (current)
- The `@kernel_function` description is what Semantic Kernel surfaces to the LLM orchestrator for tool selection and user communication — the stale `agents.yaml` value directly affects what the ReportCreation agent tells users about the output

## Proposed Solutions

### Option A
Update `presentation_export.py:118` docstring to "Generate a 5-slide PPTX tumor board summary." Update `agents.yaml:385` to reference "5-slide presentation summary" to match the current schema.

**Pros:** Eliminates the contradiction; keeps all three description sites consistent; trivial change with no logic impact
**Cons:** None
**Effort:** Trivial (< 15 minutes)
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/plugins/presentation_export.py` (line 118 docstring, confirm line 99 is already correct)
- `config/agents.yaml` (line 385)

## Acceptance Criteria

- [ ] `presentation_export.py:118` docstring updated to "5-slide"
- [ ] `agents.yaml:385` updated to "5-slide"
- [ ] `@kernel_function` description at line 99 confirmed correct (no change needed)
- [ ] No other "3-slide" string literals remain in export-related files

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
