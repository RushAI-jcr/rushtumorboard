---
status: closed
priority: p3
issue_id: "095"
tags: [code-review, architecture, quality]
dependencies: []
---

# P3 — `_LLM_TIMEOUT_SECS` defined identically in two files

## Problem Statement

`_LLM_TIMEOUT_SECS = 90.0` is defined at module level in both `presentation_export.py` (line 40) and `content_export.py` (line 58). A future change updating one but not the other creates asymmetric timeout behavior between the Word and PPTX LLM calls — surfacing as a hard-to-diagnose inconsistency where one export degrades to fallback while the other succeeds.

## Findings

Architecture agent (P3): "At two call sites in two files, this is a low-frequency maintenance burden, not an active defect." The risk is future divergence on timeout values.

`_NODE_TIMEOUT_SECS = 60.0` is only in `presentation_export.py` (specific to Node subprocess) so it does not need to be shared.

## Proposed Solution

Create a shared constants module:

**`src/scenarios/default/tools/export_constants.py`:**
```python
# Timeout values for export plugin LLM and subprocess calls
LLM_TIMEOUT_SECS = 90.0   # max wait for Azure OpenAI structured output
NODE_TIMEOUT_SECS = 60.0  # max wait for PptxGenJS subprocess
```

Both files import from there:
```python
from .export_constants import LLM_TIMEOUT_SECS as _LLM_TIMEOUT_SECS
```

## Acceptance Criteria
- [ ] `_LLM_TIMEOUT_SECS` defined in one place only
- [ ] Both `presentation_export.py` and `content_export.py` import from shared source
