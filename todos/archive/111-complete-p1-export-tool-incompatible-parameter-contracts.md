---
status: complete
priority: p1
issue_id: "111"
tags: [code-review, agent-native, architecture]
dependencies: []
---

# 111 — `export_to_word_doc` and `export_to_pptx` Have Incompatible Parameter Types for the Same Data

## Problem Statement

`export_to_word_doc` and `export_to_pptx` are always called together by the ReportCreation agent but accept different Python types for the same logical parameters. The LLM calling both tools in sequence will either:
1. Pass the correct type for one tool and the wrong type for the other (producing a runtime type error or silently incorrect output), or
2. Reformat the data between calls — which means the Word document and PPTX slide deck will have divergent representations of the same clinical facts.

The specific mismatches:
- `pathology_findings`: `list[str]` in `content_export.py` vs. `str` in `presentation_export.py`
- `clinical_trials`: `list[ClinicalTrial]` (Pydantic model) in Word doc vs. `str` in PPTX
- Word doc has `ct_scan_findings: list[str]`, `x_ray_findings: list[str]`, `medical_history: str`, `social_history: str`; PPTX accepts none of these — so the PPTX silently omits this data with no agent-visible warning

## Findings

- `content_export.py:export_to_word_doc` (line 149 signature) — `pathology_findings: list[str]`, `clinical_trials: list[ClinicalTrial]`, `ct_scan_findings: list[str]`, `x_ray_findings: list[str]`, `medical_history: str`, `social_history: str`.
- `presentation_export.py:export_to_pptx` (line 143 signature) — `pathology_findings: str`, `clinical_trials: str`. No `ct_scan_findings`, `x_ray_findings`, `medical_history`, or `social_history` parameters.
- ReportCreation agent instructions ask the agent to call both tools. The agent must reconcile incompatible type expectations with no tooling guidance.
- `list[ClinicalTrial]` in `content_export.py` requires the LLM to produce a valid Pydantic model — a fragile contract for an LLM-generated argument.

## Proposed Solution

1. **Align `pathology_findings` to `str` in both tools.** The Word doc template can split on newlines if it needs a list; the LLM treats it as plain text. This removes the list/str mismatch:

   In `content_export.py`, change `pathology_findings: list[str]` → `pathology_findings: str`. Update template rendering accordingly.

2. **Align `clinical_trials` to `str` in both tools.** Remove the `list[ClinicalTrial]` Pydantic constraint from `content_export.py`. The LLM passes a pre-formatted string; the export function renders it as-is or parses it leniently. This removes the Pydantic type-coercion requirement from the calling agent.

3. **Document the Word-only fields explicitly in `@kernel_function` descriptions.** If `ct_scan_findings`, `x_ray_findings`, `medical_history`, and `social_history` are intentionally omitted from PPTX (three-slide format space constraints), the `@kernel_function` description for `export_to_pptx` must say so clearly, and the `export_to_word_doc` description must explain these are Word-only fields. This prevents the agent from expecting symmetry where none exists.

4. **Consider a shared `ExportPayload` dataclass** that both tools accept, with PPTX ignoring fields it does not use rather than requiring the agent to construct two different argument sets.

## Acceptance Criteria

- [ ] `pathology_findings` is typed `str` in both `export_to_word_doc` and `export_to_pptx`
- [ ] `clinical_trials` is typed `str` in both export tools (no Pydantic model required from the caller)
- [ ] The `@kernel_function` descriptions for both tools explicitly document which parameters are Word-only vs. shared
- [ ] ReportCreation agent can call both tools with the same `pathology_findings` and `clinical_trials` values without reformatting between calls
- [ ] Existing Word and PPTX export tests pass after type alignment
