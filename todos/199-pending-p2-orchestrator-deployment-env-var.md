---
status: complete
priority: p2
issue_id: "199"
tags: [code-review, architecture, reliability]
dependencies: []
---

# Orchestrator Hardcoded Deployment Name Should Use Env Var

## Problem Statement

The Orchestrator agent has `deployment: gpt-4.1-mini` hardcoded in agents.yaml, while ClinicalGuidelines uses `deployment: ${AZURE_OPENAI_DEPLOYMENT_NAME_GUIDELINES}`. If a team member's Azure resource has this deployment named differently, the system fails at agent creation time with a cryptic Azure 404 error.

## Findings

**Flagged by:** Architecture Strategist (P0), Performance Oracle (P1), Security Sentinel (L-1)

All three reviewers independently flagged this inconsistency. The env-var-driven flexibility pattern established for other agents should be applied consistently.

## Proposed Solutions

### Option A: Use env var with .env.sample default (Recommended)
1. Change agents.yaml: `deployment: ${AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME}`
2. The existing `AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME` env var in `.env.sample` already documents this
3. When unset, `_resolve_env_vars_in_agents()` returns None → falls back to default deployment
- Effort: Small | Risk: None

## Acceptance Criteria

- [x] Orchestrator deployment uses env var, not hardcoded string
- [x] `.env.sample` documents the recommended value
- [x] Fallback behavior works when env var is unset

## Work Log

- 2026-04-04: Created from code review (Architecture + Performance + Security agents)
- 2026-04-04: Fixed — Changed `deployment: gpt-4.1-mini` to `deployment: ${AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME}` in agents.yaml
