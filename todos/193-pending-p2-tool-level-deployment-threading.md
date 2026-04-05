---
status: complete
priority: p2
issue_id: "193"
tags: [code-review, architecture, performance]
dependencies: []
---

# Thread Deployment Name to Tool-Level LLM Calls

## Problem Statement

6 tool plugins call `model_supports_temperature()` without passing the agent's deployment name. They fall back to the global `AZURE_OPENAI_DEPLOYMENT_NAME` instead of the deployment their parent agent's kernel uses. If any tool-bearing agent gets a reasoning-model deployment override, the tool's internal LLM calls will use wrong temperature/token settings (HTTP 400).

## Findings

**Flagged by:** Architecture Strategist, Performance Oracle, Agent-Native Reviewer

**Affected call sites:**
- `content_export/content_export.py` lines 618, 627
- `presentation_export.py` line 402
- `medical_report_extractor.py` line 206
- `oncologic_history_extractor.py` line 254
- `medical_research.py` line 562

**Currently safe** because no tool-bearing agents have deployment overrides yet (only Orchestrator and ClinicalGuidelines do, and ClinicalGuidelines' tool is lookup-based, not LLM-based).

## Proposed Solutions

### Option A: Add deployment_name to PluginConfiguration (Recommended)
- Add `deployment_name: str | None = None` to `PluginConfiguration`
- Set it from `agent_config.get("deployment")` in `_create_agent`
- Each plugin passes `self.plugin_config.deployment_name` to `model_supports_temperature()`
- Effort: Medium | Risk: Low

### Option B: Introspect kernel service
- Extract deployment from `kernel.get_service("default")` attributes
- More fragile, depends on SK internals
- Effort: Medium | Risk: Medium

## Acceptance Criteria

- [x] All 6 call sites pass the correct deployment name
- [x] Tool LLM calls use correct temperature/token params for their agent's deployment
- [ ] Existing tests pass

## Work Log

- 2026-04-04: Created from code review (Architecture + Performance + Agent-Native agents)
- 2026-04-04: Fixed — Added deployment_name to PluginConfiguration, threaded through all 6 tool plugins via create_plugin/init, updated all model_supports_temperature() calls
