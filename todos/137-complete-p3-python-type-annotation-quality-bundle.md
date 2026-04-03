---
status: pending
priority: p3
issue_id: "137"
tags: [code-review, python, quality]
dependencies: []
---

# 137 — Type annotation and Pydantic v2 quality bundle

## Problem Statement

A collection of independent type annotation gaps, Pydantic v2 anti-patterns, and class-level annotation omissions spread across the codebase. Each item is a small one-line or few-line fix; collectively they degrade static analysis coverage and introduce subtle runtime risks.

**(A)** `content_export.py` — missing `from __future__ import annotations`, present in sibling `presentation_export.py` but absent here, causing forward-reference resolution differences.

**(B)** `clinical_trials.py:93` `generate_clinical_trial_search_criteria` — missing return type annotation; docstring describes `biomarkers: str` but the parameter signature accepts `list[str]`, creating a documentation lie.

**(C)** `tumor_markers.py` `_parse_markers_raw` — returns `list[dict]` (unparameterised), losing downstream type information; should be `list[dict[str, Any]]`.

**(D)** `pretumor_board_checklist.py:167` `PreTumorBoardChecklistPlugin.__init__` — `data_access` and `chat_ctx` parameters have no type annotations.

**(E)** `medical_research.py` `MedicalResearchPlugin.__init__` — `app_ctx=None` parameter missing `AppContext | None` annotation.

**(F)** `model_utils.py:7` — docstring references a `model_name` parameter that does not exist in the function signature.

**(G)** `tumor_markers.py:158` — catches `BaseException` instead of `Exception`, suppressing `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`.

**(H)** `presentation_export.py:356` and `content_export.py:427` — use `Model(**parsed)` (Pydantic v1 style) instead of `Model.model_validate(parsed)` (Pydantic v2).

**(I)** `tumor_board_summary.py:54` — mutable list default on a Pydantic field should use `Field(default_factory=list)`.

**(J)** `medical_report_extractor.py:44-47` — class-level configuration attributes lack `ClassVar` annotation, making Pydantic treat them as instance fields.

**(K)** `nccn_guidelines.py:37-42` — mutable class-level dicts lack `ClassVar` annotation; same Pydantic mis-classification risk.

## Findings

- `content_export.py` — missing `from __future__ import annotations`
- `clinical_trials.py:93` — missing return type; docstring/signature biomarkers type mismatch
- `tumor_markers.py` `_parse_markers_raw` — `list[dict]` return type
- `pretumor_board_checklist.py:167` — untyped `data_access`, `chat_ctx`
- `medical_research.py` `MedicalResearchPlugin.__init__` — `app_ctx` unannotated
- `model_utils.py:7` — stale `model_name` parameter in docstring
- `tumor_markers.py:158` — `BaseException` catch
- `presentation_export.py:356`, `content_export.py:427` — `Model(**parsed)` Pydantic v1 pattern
- `tumor_board_summary.py:54` — mutable list default without `default_factory`
- `medical_report_extractor.py:44-47` — class attributes missing `ClassVar`
- `nccn_guidelines.py:37-42` — class-level dicts missing `ClassVar`

## Proposed Solution

Fix each item independently; bundle into a single commit. Key changes:

- Add `from __future__ import annotations` to `content_export.py`
- Add return type to `generate_clinical_trial_search_criteria`; reconcile docstring with actual `list[str]` type
- Change `list[dict]` to `list[dict[str, Any]]` in `_parse_markers_raw`
- Annotate `data_access`, `chat_ctx`, and `app_ctx` parameters
- Remove stale `model_name` from `model_utils.py` docstring
- Change `BaseException` to `Exception` at `tumor_markers.py:158`
- Replace `Model(**parsed)` with `Model.model_validate(parsed)` in both export files
- Change mutable list default to `Field(default_factory=list)` in `tumor_board_summary.py`
- Add `ClassVar` annotations to class-level attributes in `medical_report_extractor.py` and `nccn_guidelines.py`

## Acceptance Criteria

- [ ] `content_export.py` includes `from __future__ import annotations`
- [ ] All listed return-type and parameter-type gaps are annotated
- [ ] `Model.model_validate(parsed)` used everywhere instead of `Model(**parsed)`
- [ ] `ClassVar` applied to all class-level shared state in Pydantic models
- [ ] `BaseException` replaced with `Exception` in `tumor_markers.py:158`
- [ ] `Field(default_factory=list)` used for mutable list defaults in Pydantic models
- [ ] Docstring in `model_utils.py` no longer references non-existent parameter
