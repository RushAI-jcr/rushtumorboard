---
name: Pathology and Radiology agents need data_source_layer caveat instructions
description: data_source_layer/data_source_description metadata is generated but agents have no instructions to surface data quality caveats to the tumor board
type: feature
status: complete
priority: p2
issue_id: "020"
tags: [agent-instructions, clinical-safety, code-review]
---

## Problem Statement

`MedicalReportExtractorBase._extract()` now injects three metadata fields into every tool response:
- `data_source_layer`: 1 (dedicated CSV), 2 (operative/procedure notes), or 3 (keyword-matched clinical notes)
- `data_source_description`: human-readable description of the fallback layer used
- `truncation_note`: (optional) when >25 sources were available and capped

These fields contain critical clinical safety information. Layer 3 extraction means pathology findings came from a progress note where a physician summarized results — NOT from a dedicated pathology report. A tumor board making treatment decisions on Layer 3 data should know they are working from secondary sources.

**The gap:** Nothing in `src/scenarios/default/config/agents.yaml` tells the Pathology or Radiology agents to check these fields or present a caveat to the tumor board. Without instructions, the LLM may or may not surface this information, and when it does, it will be inconsistent.

**Clinical risk:** A clinician assumes they are seeing a structured pathology report when in fact the LLM extracted from a narrative progress note summary. This could affect treatment decisions.

## Proposed Solution

Add a paragraph to the Pathology agent instructions in `agents.yaml`:

```
When presenting pathology findings, check the data_source_layer field:
- Layer 1 (Dedicated report CSV): Present normally.
- Layer 2 (operative/procedure notes) or Layer 3 (keyword-matched clinical notes):
  Prominently note: "⚠ Pathology findings extracted from [data_source_description],
  not a dedicated pathology report. Results should be confirmed with the pathology
  department before treatment decisions."
If truncation_note is present, add: "Note: [truncation_note]"
```

Same addition for the Radiology agent instructions, referencing radiology-specific source types.

**Affected file:** `src/scenarios/default/config/agents.yaml` — Pathology and Radiology agent instruction blocks.

## Acceptance Criteria
- [ ] Pathology agent instructions include data_source_layer caveat language
- [ ] Radiology agent instructions include data_source_layer caveat language
- [ ] Test: simulate a Layer 2/3 extraction and verify agent output includes caveat

## Work Log
- 2026-04-02: Identified by agent-native-reviewer during code review. The metadata fields are generated but not instructed — a critical gap for clinical safety.
- 2026-04-02: Implemented and marked complete.
