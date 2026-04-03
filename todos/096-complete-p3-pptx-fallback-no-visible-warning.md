---
status: complete
priority: p3
issue_id: "096"
tags: [code-review, clinical-safety, usability]
dependencies: []
---

# P3 — PPTX fallback `SlideContent` has no visible degradation indicator

## Problem Statement

When `_summarize_for_slides` uses the fallback `SlideContent` (LLM timeout or schema mismatch), the slide deck is generated with raw truncated text and no visible signal that clinical content may be incomplete. The Word doc fallback includes `"[FALLBACK] Export used LLM fallback — review all fields before printing."` in `action_items`. The PPTX has no equivalent — a clinician may not notice the deck is degraded.

## Findings

Performance agent: "A silently degraded slide deck is a patient safety concern because a clinician may not notice the fallback output was used."

Current PPTX fallback (`presentation_export.py`, lines 324-348): `discussion_bullets` contains truncated raw treatment_plan and board_discussion strings — no indicator this is fallback content.

The `content_export.py` fallback was corrected in this PR to include the warning. The PPTX fallback was not.

## Proposed Solution

Add a visible indicator to the fallback `SlideContent`:

```python
discussion_bullets=[
    "[FALLBACK] LLM summarization failed — verify all fields before presenting.",
    all_data.get("treatment_plan", "No treatment plan")[:80],
    all_data.get("board_discussion", "")[:80],
],
```

Also add to `patient_bullets`:
```python
patient_bullets=[
    "[FALLBACK — VERIFY]",
    f"Age: {all_data.get('patient_age', 'N/A')}",
    f"Cancer: {all_data.get('cancer_type', 'N/A')}",
],
```

## Acceptance Criteria
- [ ] PPTX fallback `SlideContent.discussion_bullets` includes `[FALLBACK]` as first bullet
- [ ] PPTX fallback `SlideContent.patient_bullets` includes `[FALLBACK — VERIFY]`
- [ ] `export_to_pptx` return string notes fallback was used when applicable
