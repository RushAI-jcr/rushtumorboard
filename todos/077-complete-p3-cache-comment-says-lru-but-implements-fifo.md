---
status: pending
priority: p3
issue_id: "077"
tags: [code-review, documentation, caching, correctness]
dependencies: []
---

## Problem Statement

All three fallback accessor classes (`ClinicalNoteAccessor`, `FhirClinicalNoteAccessor`, `FabricClinicalNoteAccessor`) have comments saying `# LRU eviction` on the cache eviction code, but the implementation is FIFO (First-In, First-Out):

```python
# LRU eviction  ← incorrect label
if len(self._note_cache) >= self._CACHE_MAX_PATIENTS:
    oldest = next(iter(self._note_cache))
    del self._note_cache[oldest]
self._note_cache[patient_id] = notes
```

This deletes the key that was *first inserted*, not the *least recently used* key. A true LRU cache would update the access order on every cache hit. `CaboodleFileAccessor` uses `collections.OrderedDict` with `move_to_end` for proper LRU — the other three use plain `dict` with a FIFO eviction label.

At the current scale (max 5 patients in cache), this distinction has no clinical impact. But the incorrect label could mislead developers adding features that assume LRU behavior.

## Findings

- **File:** `src/data_models/clinical_note_accessor.py` — cache eviction comment
- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py` — cache eviction comment
- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py` — cache eviction comment
- **Reported by:** code-simplicity-reviewer
- **Severity:** P3 — documentation correctness

## Proposed Solutions

### Option A (Minimal): Correct the comment
```python
# FIFO eviction (oldest inserted patient dropped when capacity reached)
```

### Option B: Switch to true LRU using OrderedDict
```python
from collections import OrderedDict
self._note_cache: OrderedDict[str, list[str]] = OrderedDict()

# On cache hit:
self._note_cache.move_to_end(patient_id)

# On eviction:
self._note_cache.popitem(last=False)  # remove oldest-accessed
```

Option A is sufficient for the current use case.

## Acceptance Criteria

- [ ] Cache eviction comments accurately describe the eviction strategy (FIFO or LRU)
- [ ] If comment is changed to FIFO, no code claims LRU behavior

## Work Log

- 2026-04-02: Identified during code review.
