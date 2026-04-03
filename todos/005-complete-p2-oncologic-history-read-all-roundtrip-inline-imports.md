---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, performance, python-quality, simplicity]
dependencies: []
---

## Problem Statement

`oncologic_history_extractor.py` has two related issues in `_get_clinical_notes` and `_extract`:

1. **Serialize/deserialize roundtrip:** `_get_clinical_notes` calls `accessor.read_all()` which JSON-serializes every note to a string, then immediately deserializes every string back to a dict. This is a pure waste — `read_all()` is designed for passing to LLM context directly, not for immediate parsing. `get_clinical_notes_by_type()` already exists and returns `list[dict]` directly.

2. **Inline imports inside `_extract`:** `import json`, `import textwrap`, `import logging`, and three Semantic Kernel imports are inside the `_extract` method body (lines 139-147). Python caches these after the first call but they add visual noise, mislead readers about scoping requirements, and the `logger = logging.getLogger(__name__)` inside the method creates a new logger object on every call (though `getLogger` deduplicates by name). A module-level `logger` already exists in the file from line 148 being `logger = logging.getLogger(__name__)`.

## Findings

- **File:** `src/scenarios/default/tools/oncologic_history_extractor.py`
- **Lines:** 119-135 (roundtrip), 139-147 (inline imports)
- **Reported by:** code-simplicity-reviewer, performance-oracle, kieran-python-reviewer
- **Severity:** P2 — measurable overhead on hot path; code clarity issue

## Proposed Solutions

### Option A (Recommended): Use get_clinical_notes_by_type + module-level imports

**Fix `_get_clinical_notes`:**
```python
async def _get_clinical_notes(self, patient_id: str) -> list[dict]:
    accessor = self.data_access.clinical_note_accessor
    
    if hasattr(accessor, "get_clinical_notes_by_type"):
        notes = await accessor.get_clinical_notes_by_type(
            patient_id, list(self._RELEVANT_NOTE_TYPES)
        )
    else:
        # Fallback for non-Caboodle accessors
        all_notes_json = await accessor.read_all(patient_id)
        notes = []
        for note_json in all_notes_json:
            note = json.loads(note_json) if isinstance(note_json, str) else note_json
            if note.get("note_type", note.get("NoteType", "")).lower() in self._RELEVANT_NOTE_TYPES:
                notes.append(note)
    
    notes.sort(
        key=lambda n: n.get("date", n.get("EntryDate", n.get("OrderDate", ""))),
        reverse=True,
    )
    return notes[:self.MAX_NOTES]
```

**Move inline imports to module top (remove lines 139-147 from inside `_extract`, add to top of file):**
```python
# Add to top of oncologic_history_extractor.py:
import json
import textwrap
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory

logger = logging.getLogger(__name__)  # already at module level, remove from inside _extract
```

- **Effort:** Small
- **Risk:** Low — `get_clinical_notes_by_type` is now available on `CaboodleFileAccessor`; fallback path preserved for FHIR/Fabric accessors

## Recommended Action

Option A — eliminates the roundtrip and moves imports to module level.

## Technical Details

- **Affected file:** `src/scenarios/default/tools/oncologic_history_extractor.py`
- **Lines:** 119-147

## Acceptance Criteria

- [ ] `_get_clinical_notes` uses `get_clinical_notes_by_type` when available
- [ ] Fallback to `read_all` + manual filter when accessor doesn't have the method
- [ ] All imports at module level (none inside methods)
- [ ] Single `logger` at module level, not re-created inside `_extract`
- [ ] Tests still pass

## Work Log

- 2026-04-02: Identified by performance-oracle, code-simplicity-reviewer, and kieran-python-reviewer
