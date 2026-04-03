---
status: pending
priority: p2
issue_id: "125"
tags: [code-review, python, quality]
dependencies: []
---

# 125 — `create_plugin` factory in `clinical_trials.py` has wrong return type; others have no annotation

## Problem Statement

`create_plugin` in `clinical_trials.py:61` is annotated `-> Kernel` but returns a `ClinicalTrialsPlugin` instance. This is a hard Pyright type error. Additionally, multiple other `create_plugin` factory functions across the codebase — `content_export.py:128`, `medical_research.py:125`, `nccn_guidelines.py:25`, `pretumor_board_checklist.py:154` — are missing return type annotations entirely. These functions are the primary entry points for plugin construction; missing or wrong return types prevent Pyright from catching misconfigured plugin usages and reduce IDE discoverability.

## Findings

- `clinical_trials.py:61` — annotated `-> Kernel`, returns `ClinicalTrialsPlugin` (hard Pyright error)
- `content_export.py:128` — `create_plugin` missing return type annotation
- `medical_research.py:125` — `create_plugin` missing return type annotation
- `nccn_guidelines.py:25` — `create_plugin` missing return type annotation
- `pretumor_board_checklist.py:154` — `create_plugin` missing return type annotation

## Proposed Solution

1. Fix `clinical_trials.py:61`: change annotation from `-> Kernel` to `-> "ClinicalTrialsPlugin"` (or import the class if not already imported at that scope).
2. Add correct return type annotations to all five `create_plugin` functions, each returning the specific plugin class they instantiate.
3. Run `pyright` after changes to confirm zero errors on these functions.

## Acceptance Criteria

- [ ] `create_plugin` in `clinical_trials.py` is annotated `-> ClinicalTrialsPlugin` and Pyright reports no error
- [ ] All five `create_plugin` functions listed in Findings have explicit return type annotations
- [ ] No new Pyright errors introduced by the annotation additions
- [ ] Return type annotations use the concrete plugin class, not `Any` or `object`
