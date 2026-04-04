---
status: pending
priority: p3
issue_id: "183"
tags: [code-review, architecture, agent-orchestration]
dependencies: []
---

# HealthcareAgent Channel Does Not Use CustomHistoryChannel

## Problem Statement

`src/healthcare_agents/agent.py` line 123: `HealthcareAgent.create_channel()` returns a plain `HealthcareAgentChannel`, not the `CustomHistoryChannel`. If HealthcareAgents are re-enabled in `agents.yaml`, their channel will not benefit from tool-message filtering or truncation, potentially causing OpenAI 400 errors from orphaned tool messages.

## Findings

- **Source**: Architecture Strategist (P3), Agent-Native Reviewer (Warning #7)
- **Evidence**: `healthcare_agents/agent.py` create_channel() returns HealthcareAgentChannel
- **Current state**: Healthcare agents are disabled in agents.yaml
- **Risk**: Only relevant if re-enabled

## Proposed Solutions

### Option A: Document the gap (Recommended for now)
- Add a comment in agents.yaml and healthcare_agents/agent.py noting that re-enabling requires CustomHistoryChannel compatibility
- **Effort**: Small (5 min)

### Option B: Add tool-message filtering to HealthcareAgentChannel
- Apply the same filtering logic when healthcare agents are re-enabled
- **Effort**: Medium (30 min)

## Acceptance Criteria
- [ ] Documentation or code comment warns about channel parity gap
