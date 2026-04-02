---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, performance, llm-context, token-limit]
dependencies: []
---

## Problem Statement

`PatientDataPlugin.create_timeline()` and `process_prompt()` in `patient_data.py` call `read_all()` and pass the entire result as `json.dumps(files)` in an LLM system message — with no volume cap. `read_all` returns all notes from three file types (clinical notes, pathology reports, radiology reports). For a patient with 260-405 notes at ~4 KB each, this is 1-1.6 MB of text = 250,000-400,000 tokens — well over Azure GPT-4o's 128K token limit.

All specialized extractors (pathology, radiology, oncologic history) have tight volume caps (MAX_REPORTS=25, MAX_CHARS=80K). The base `PatientDataPlugin` functions do not.

## Findings

- **File:** `src/scenarios/default/tools/patient_data.py`
- **Lines:** 89, 114, 170, 178
- **Reported by:** performance-oracle
- **Severity:** P2 — will cause Azure OpenAI API errors or silent truncation on high-volume patients

## Proposed Solutions

### Option A (Recommended): Apply a volume cap before passing to LLM

```python
# In create_timeline and process_prompt, after reading files:
_MAX_TIMELINE_NOTES = 75  # ~300KB of text, well within 128K token limit

files = clinical_note_metadatas + image_metadatas  # from get_metadata_list
notes_json = await self.data_access.clinical_note_accessor.read_all(patient_id)

# Cap before sending to LLM
if len(notes_json) > _MAX_TIMELINE_NOTES:
    logger.info(
        "Capping patient data notes from %d to %d for patient %s",
        len(notes_json), _MAX_TIMELINE_NOTES, patient_id
    )
    notes_json = notes_json[:_MAX_TIMELINE_NOTES]

files_text = json.dumps(notes_json)
```

### Option B: Use get_clinical_notes_by_type with curated types
Instead of `read_all`, call `get_clinical_notes_by_type` with a focused list to retrieve only note-type data relevant for timelines, avoiding radiology/pathology report text that the timeline function doesn't need.

- **Effort:** Small-Medium
- **Risk:** Low — adds a cap and logging; does not change behavior for typical patients

## Recommended Action

Option A — consistent with cap pattern already in all specialized extractors.

## Technical Details

- **Affected file:** `src/scenarios/default/tools/patient_data.py` lines 89, 114, 170, 178

## Acceptance Criteria

- [ ] `create_timeline` caps notes before passing to LLM
- [ ] `process_prompt` caps notes before passing to LLM  
- [ ] Truncation is logged at INFO level with count
- [ ] No Azure OpenAI API errors when running against high-volume patients

## Work Log

- 2026-04-02: Identified by performance-oracle during code review
