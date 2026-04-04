---
status: pending
priority: p2
issue_id: "185"
tags: [code-review, agent-native, prompt-engineering]
dependencies: []
---

# Clarify PatientStatus prompt wording for pathology data access

## Problem Statement
The PatientStatus agent's DATA SOURCES table states it reads `pathology_reports.csv` as Tier 1 for tumor markers. This wording implies the agent has direct CSV file access, but the agent actually accesses pathology data *through* the `get_tumor_marker_trend` tool. This misleading phrasing could confuse the LLM into attempting to load the CSV file directly (e.g., generating code to read the file, or hallucinating file contents), reducing reliability and potentially causing failed tool invocations.

## Findings
- **Source**: Agent-Native Reviewer (P2)
- `src/scenarios/default/config/agents.yaml` -- PatientStatus agent DATA SOURCES section references `pathology_reports.csv` without clarifying access mechanism

## Proposed Solutions
1. **Update wording to reference the tool**
   - Change `pathology_reports.csv` to `pathology_reports.csv (accessed via get_tumor_marker_trend tool)`
   - Pros: Precise, prevents LLM confusion, minimal change
   - Cons: None
   - Effort: ~5 minutes

2. **Restructure DATA SOURCES to separate data from access method**
   - Add an "Access Method" column to the DATA SOURCES table: `| pathology_reports.csv | Tier 1 | get_tumor_marker_trend |`
   - Pros: Systematic, scales to other data sources
   - Cons: Larger prompt change, needs review of all data source entries
   - Effort: ~20 minutes

## Acceptance Criteria
- [ ] PatientStatus DATA SOURCES section clarifies that `pathology_reports.csv` is accessed via the `get_tumor_marker_trend` tool
- [ ] Wording does not imply direct file access
- [ ] Agent behavior is unchanged (tool invocation patterns remain the same)
- [ ] YAML syntax is valid after the edit
