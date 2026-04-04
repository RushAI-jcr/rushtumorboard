---
name: _JSON_FENCE_RE and _LAYER_DESCRIPTIONS placement violate PEP 8
description: Module-level constants defined between stdlib imports and third-party imports; also _LAYER_DESCRIPTIONS should be a class constant not inline dict
type: quality
status: complete
priority: p3
issue_id: "022"
tags: [code-quality, pep8, code-review]
---

## Problem Statement

**Issue 1 — `_JSON_FENCE_RE` placement:**

`medical_report_extractor.py` currently has:
```python
import json
import logging
import re          # stdlib
import textwrap

_JSON_FENCE_RE = re.compile(...)   # ← constant here, between stdlib and third-party

from semantic_kernel...             # third-party
```

PEP 8 says: stdlib imports → blank line → third-party imports → blank line → local imports → blank line → module constants. The constant breaks the import block.

**Issue 2 — `data_source_description` inline dict in `_extract`:**

The description dict is reconstructed on every call:
```python
findings["data_source_description"] = {
    1: "Dedicated report CSV",
    2: "Domain-specific clinical notes (operative/procedure notes)",
    3: "Keyword-matched general clinical notes (progress notes, H&P, consults)",
}.get(source_layer, "Unknown")
```

This dict belongs to the class conceptually (it documents the layers defined by the class constants `layer2_note_types`/`layer3_note_types`). The `.get(..., "Unknown")` fallback is unreachable dead code — `source_layer` can only be 1, 2, or 3 at that point. If it were ever outside that range, a `KeyError` is the correct signal, not a silent `"Unknown"` in clinical output.

## Proposed Solution

**Fix 1:** Move `_JSON_FENCE_RE` after all imports:
```python
import json
import logging
import re
import textwrap

from semantic_kernel...
from data_models...

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
```

**Fix 2:** Promote to class constant on `MedicalReportExtractorBase`:
```python
class MedicalReportExtractorBase:
    ...
    _LAYER_DESCRIPTIONS: dict[int, str] = {
        1: "Dedicated report CSV",
        2: "Domain-specific clinical notes (operative/procedure notes)",
        3: "Keyword-matched general clinical notes (progress notes, H&P, consults)",
    }
```

Then in `_extract`: `findings["data_source_description"] = self._LAYER_DESCRIPTIONS[source_layer]`
(No `.get()` — a missing key is a bug, not a normal case.)

**Effort:** Tiny (2 edits, no logic change)

## Acceptance Criteria
- [ ] `_JSON_FENCE_RE` appears after all import blocks
- [ ] `_LAYER_DESCRIPTIONS` is a class constant; inline dict removed from `_extract`
- [ ] No `.get(..., "Unknown")` in `_extract`

## Work Log
- 2026-04-02: Identified by kieran-python-reviewer and code-simplicity-reviewer during code review.
- 2026-04-02: Implemented and marked complete.
