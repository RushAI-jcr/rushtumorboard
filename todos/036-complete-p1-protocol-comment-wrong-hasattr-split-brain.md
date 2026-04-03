---
name: protocol-comment-wrong-hasattr-split-brain
description: Stale protocol comment and inconsistent hasattr guards create split-brain calling convention across agents
type: code-review
status: complete
priority: p1
issue_id: 036
tags: [code-review, architecture, protocol]
---

## Problem Statement
`clinical_note_accessor_protocol.py` lines 12-13 comment says "Gate with hasattr() before calling" and "NOT Fabric" — but FabricClinicalNoteAccessor now fully implements `get_clinical_notes_by_type` and `get_clinical_notes_by_keywords`. Meanwhile `tumor_markers.py`, `patient_data.py`, and `medical_report_extractor.py` call protocol methods directly (no hasattr), while `pretumor_board_checklist.py` and `oncologic_history_extractor.py` still use hasattr guards. This creates a split-brain calling convention where some callers are safe and others are not, with no way to know which. If any future accessor is added without these methods, direct callers will raise AttributeError silently.

## Findings
- `src/data_models/clinical_note_accessor_protocol.py:11-13`: Comment instructs callers to gate with hasattr() and states Fabric does not implement the extended methods — both statements are now false.
- `src/scenarios/default/tools/pretumor_board_checklist.py:238-257`: Uses hasattr guard before calling `get_clinical_notes_by_type` and `get_clinical_notes_by_keywords`.
- `src/scenarios/default/tools/oncologic_history_extractor.py:148`: Uses hasattr guard before calling protocol methods.
- `src/scenarios/default/tools/tumor_markers.py`, `patient_data.py`, `medical_report_extractor.py`: Call protocol methods directly with no hasattr guard.

## Proposed Solutions
### Option A
Update protocol comment to state all methods are universally implemented; remove hasattr guards from `pretumor_board_checklist.py` and `oncologic_history_extractor.py` to unify the calling convention.

**Pros:** Single consistent calling convention; comment accurately reflects reality; simpler call sites
**Cons:** If a new accessor is ever added without full implementation, direct callers will raise AttributeError (but Protocol enforcement should catch this at type-check time)
**Effort:** Small
**Risk:** Low

### Option B
Keep hasattr guards everywhere — restore them in `tumor_markers.py`, `medical_report_extractor.py`, and `patient_data.py`.

**Pros:** Defensive; tolerates partially-implemented accessors; consistent across all callers
**Cons:** hasattr guards mask Protocol violations; adds boilerplate noise; contradicts the Protocol pattern
**Effort:** Small
**Risk:** Low

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/data_models/clinical_note_accessor_protocol.py:11-13`
- `src/scenarios/default/tools/pretumor_board_checklist.py:238-257`
- `src/scenarios/default/tools/oncologic_history_extractor.py:148`
- `src/scenarios/default/tools/tumor_markers.py`
- `src/scenarios/default/tools/patient_data.py`
- `src/scenarios/default/tools/medical_report_extractor.py`

## Acceptance Criteria
- [ ] Protocol comment accurately reflects which accessors implement each method
- [ ] All callers use a single consistent convention (either all use hasattr or none do)
- [ ] Mypy/pyright reports no Protocol compliance errors for any accessor
- [ ] A new accessor added without full implementation is caught at type-check time, not runtime

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
