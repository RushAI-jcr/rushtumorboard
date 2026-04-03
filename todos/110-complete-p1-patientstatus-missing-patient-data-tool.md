---
status: complete
priority: p1
issue_id: "110"
tags: [code-review, agent-native, architecture]
dependencies: []
---

# 110 — PatientStatus Agent Cannot Reliably Supply `cancer_type` to Checklist; Orchestrator Calls Checklist Before Type Is Known

## Problem Statement

Two related agent configuration issues cause the pre-tumor-board checklist to silently evaluate every patient using incorrect conditional criteria:

**Issue A — Missing tool access.** The PatientStatus agent (`agents.yaml:PatientStatus`) does not have `patient_data` in its tools list, yet its instructions require it to determine `cancer_type` from PatientHistory and Pathology agents. `get_pretumor_board_checklist` requires `cancer_type` as a parameter. If PatientHistory has not yet responded in the conversation (which is guaranteed by Issue B), PatientStatus has no mechanism to retrieve the cancer type and must either hallucinate it or stall waiting for context that has not been populated.

**Issue B — Checklist called before cancer type is established.** The Orchestrator's Step 0 directs PatientStatus to run `get_pretumor_board_checklist` before steps a–i, which includes the PatientHistory and OncologicHistory loading steps. At the moment the checklist is called, `cancer_type` is unknown. The default value falls through to "ovarian" for every patient. This means mucinous, germ-cell, endometrial, and cervical patients all receive the ovarian conditional checklist items (e.g., CA-125 threshold checks, bevacizumab eligibility criteria) and miss their own cancer-type-specific items. There is no visible error — the checklist runs and returns results, just for the wrong cancer type.

## Findings

- `agents.yaml:PatientStatus` — tools list does not include `patient_data`. The agent instructions reference `cancer_type` as a required input to checklist logic.
- `agents.yaml:Orchestrator` — Step 0 positions `get_pretumor_board_checklist` before the history-loading steps (steps a–i). At Step 0, no agent has loaded patient history, so `cancer_type` is unavailable from conversation context.
- `get_pretumor_board_checklist` — `cancer_type` parameter defaults to `"ovarian"` when not supplied or when the caller hallucinates a value. Conditional checklist items for mucinous, germ-cell, and non-GYN tumor types are gated on this parameter.

## Proposed Solution

**Option A — Add `patient_data` tool to PatientStatus** so the agent can retrieve cancer type directly without relying on prior agent messages:

In `agents.yaml`, under `PatientStatus.tools`, add:
```yaml
- patient_data
```

Update PatientStatus instructions to specify that it must call `load_patient_data` and extract `cancer_type` from OncologicHistory data before calling `get_pretumor_board_checklist`.

**Option B — Move checklist call to after history agents complete** (the structural fix):

In the Orchestrator instructions, reorder so that `get_pretumor_board_checklist` is called after steps a–i (PatientHistory and OncologicHistory loading) are confirmed complete. The checklist then reads `cancer_type` from the established conversation context.

**Recommended:** Apply both fixes. Option A provides tool-level access as a fallback; Option B fixes the sequencing so the checklist is never called speculatively.

## Acceptance Criteria

- [ ] PatientStatus agent can supply a correct, data-derived `cancer_type` to `get_pretumor_board_checklist` (not a hallucinated or defaulted value)
- [ ] `get_pretumor_board_checklist` is called in the Orchestrator flow only AFTER PatientHistory and OncologicHistory agents have confirmed the cancer type
- [ ] Mucinous, germ-cell, endometrial, and cervical patients receive cancer-type-specific (not generic ovarian) conditional checklist items
- [ ] An integration test verifies checklist output for a germ-cell patient includes germ-cell-specific items and excludes ovarian-only items
