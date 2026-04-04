---
status: pending
priority: p2
issue_id: "157"
tags: [code-review, architecture, agent-native, mcp]
dependencies: []
---

# MCP/SK Tool Parity Gap: study_statistics and keyword_search

## Problem Statement

The MCP server (`clinical_trials_mcp.py`) exposes 6 tools, but the SK plugin bridge (`clinical_trials_nci.py`) only wraps 4. The `get_study_statistics` and `search_trials_by_keyword` tools are available to MCP clients (Copilot Studio) but not to internal SK agents.

## Findings

- **Source**: Agent-Native Reviewer
- **Evidence**: `src/mcp_servers/clinical_trials_mcp.py` (6 tools) vs `src/scenarios/default/tools/clinical_trials_nci.py` (4 wrappers)
- **Related**: todos/147-complete-p3-clinical-trials-mcp-tool-name-mismatch.md

## Proposed Solutions

### Option A: Add SK wrappers for missing tools (Recommended)
Add `study_statistics` and `keyword_search` wrappers to `clinical_trials_nci.py`. Update `agents.yaml` ClinicalTrials instructions.
- **Effort**: Medium
- **Risk**: Low

### Option B: Document as intentionally MCP-only
- **Effort**: Small
- **Risk**: Parity gap persists

## Acceptance Criteria
- [ ] ClinicalTrials agent can call all 6 MCP tools via SK plugins
- [ ] agents.yaml instructions updated to reference new tools

## Work Log
- 2026-04-02: Identified during code review (agent-native-reviewer)
