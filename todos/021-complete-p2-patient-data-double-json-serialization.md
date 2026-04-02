---
name: patient_data.py double JSON serialization in create_timeline and process_prompt
description: Caboodle path does json.dumps() per note then json.dumps(files) — double-encoding creates escaped JSON strings that increase token cost and may degrade LLM extraction quality
type: performance
status: complete
priority: p2
issue_id: "021"
tags: [performance, llm-quality, code-review]
---

## Problem Statement

In `create_timeline` and `process_prompt`, when `get_clinical_notes_by_type` is available (Caboodle path), the filtered notes are already `list[dict]`. The code converts them to a list of JSON strings, then serializes that list:

```python
# current (Caboodle path)
filtered = await accessor.get_clinical_notes_by_type(patient_id, TIMELINE_NOTE_TYPES)
files = [json.dumps(r) for r in filtered]          # → list[str], each is a JSON string
# ...
chat_history.add_system_message("..." + json.dumps(files))  # → JSON array of JSON strings
```

The LLM receives a JSON array where every element is a string containing *escaped* JSON, not a JSON array of objects. For example:
```json
["{\"id\": \"N001\", \"text\": \"Patient presented...\"}", ...]
```
instead of:
```json
[{"id": "N001", "text": "Patient presented..."}, ...]
```

**Impact:**
1. **Token inflation**: escape sequences add ~15-20% to payload size. At 75 notes × 4 KB each = 300 KB baseline → 345-360 KB after double-encoding.
2. **LLM quality**: the model must parse escaped JSON strings rather than native objects, adding unnecessary cognitive load and potential misparse risk.
3. **Cost**: ~15-20% more tokens per call × 2 tool functions × every PatientHistory request.

**Note:** The legacy `read_all()` path (non-Caboodle) correctly returns `list[str]` (pre-serialized JSON strings), so the double-encoding is specific to the Caboodle fast path introduced in this refactor.

**Affected file:** `src/scenarios/default/tools/patient_data.py`, `create_timeline` (~line 157) and `process_prompt` (~line 261).

## Proposed Solution

For the Caboodle path, skip the per-note `json.dumps()` and pass the dicts directly:

```python
if hasattr(accessor, "get_clinical_notes_by_type"):
    filtered = await accessor.get_clinical_notes_by_type(patient_id, TIMELINE_NOTE_TYPES)
    notes_payload = filtered  # list[dict] — serialize once below
    if not notes_payload:
        notes_payload = [json.loads(s) for s in await accessor.read_all(patient_id)]
else:
    notes_payload = [json.loads(s) for s in await accessor.read_all(patient_id)]

# Single serialization:
chat_history.add_system_message("You have access to the following patient history:\n" + json.dumps(notes_payload))
```

This requires the legacy `read_all()` path to also deserialize to dicts first (one extra parse step), but eliminates the double-encode for the common Caboodle path.

**Alternative (simpler):** Just use `files` as-is for the legacy path (list of strings) and change only the Caboodle path to not call `[json.dumps(r) for r in filtered]`. The downstream `json.dumps(files)` would then produce `["...", "..."]` for the legacy path and `[{...}, {...}]` for the Caboodle path — inconsistent but both valid JSON. Document the inconsistency.

**Effort:** Small-Medium (need to verify LLM consumption of both formats)

## Acceptance Criteria
- [ ] Caboodle path does not double-serialize notes
- [ ] LLM receives valid JSON objects, not escaped strings
- [ ] Token count per `create_timeline` call is measurably reduced (log comparison)
- [ ] Existing timeline tests pass

## Work Log
- 2026-04-02: Identified by performance-oracle during code review. The double-serialization was introduced when `get_clinical_notes_by_type` (returning dicts) was added as a fast path for a `read_all()` pattern that expected strings.
- 2026-04-02: Implemented and marked complete.
