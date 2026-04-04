---
name: no-note-cache-fallback-accessors-read-all-every-call
description: Fallback accessors call read_all() on every invocation with no cache — 7.5MB+ redundant network egress per session
type: code-review
status: complete
priority: p1
issue_id: 037
tags: [code-review, performance, caching]
---

## Problem Statement
`get_clinical_notes_by_type` in three fallback accessors (ClinicalNoteAccessor/blob, FhirClinicalNoteAccessor, FabricClinicalNoteAccessor) calls `read_all()` unconditionally on every invocation with no per-patient note cache. `get_clinical_notes_by_keywords` chains on top, causing a second `read_all()` call. `read_all` downloads all notes from Azure Blob / FHIR API before filtering in Python. Additionally, `json.loads()` is called per-note in a loop, parsing notes that are immediately discarded on type mismatch. For 150 notes at 5KB each: 750KB network egress per call; 10 agents × multiple calls = 7.5MB+ redundant egress per session. By contrast, CaboodleFileAccessor already has LRU caching.

## Findings
- `src/data_models/clinical_note_accessor.py:81-95`: `get_clinical_notes_by_type` calls `self.read_all()` with no caching; every invocation downloads all blobs.
- `src/data_models/fhir/fhir_clinical_note_accessor.py:212-230`: Same pattern — `read_all()` called unconditionally per invocation.
- `src/data_models/fabric/fabric_clinical_note_accessor.py:151-165`: Same pattern — no caching layer before type/keyword filtering.
- All three: `json.loads()` executed per note in loop, parsing notes discarded immediately on type mismatch.

## Proposed Solutions
### Option A
Add instance-level `_note_cache: dict[str, list[dict]]` to each class; populate on first `read_all()`; subsequent `get_clinical_notes_by_type` and `get_clinical_notes_by_keywords` calls filter over cached dicts (no additional `read_all()` or `json.loads()` needed).

**Pros:** Eliminates all redundant egress within a session; shared cache between type and keyword queries; mirrors CaboodleFileAccessor behavior; no external dependency
**Cons:** Cache is per-instance (not cross-request); requires explicit invalidation hook if notes update mid-session (not currently a concern)
**Effort:** Medium
**Risk:** Low

### Option B
Add caching only to `get_clinical_notes_by_type` using `functools.lru_cache` (simpler, single method).

**Pros:** Very small change; lru_cache handles invalidation automatically if args change
**Cons:** Does not share cache with `get_clinical_notes_by_keywords`; second redundant `read_all()` still occurs for keyword queries; lru_cache on instance methods requires workaround
**Effort:** Small
**Risk:** Low

### Option C
Accept current behavior since blob/FHIR/Fabric are not the primary data path (Caboodle is); add TODO comment documenting the limitation.

**Pros:** Zero implementation risk; no code change
**Cons:** Redundant egress continues; problem compounds if Fabric becomes primary path; leaves a known performance regression undocumented except in a comment
**Effort:** Small
**Risk:** Low

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/data_models/clinical_note_accessor.py:81-95`
- `src/data_models/fhir/fhir_clinical_note_accessor.py:212-230`
- `src/data_models/fabric/fabric_clinical_note_accessor.py:151-165`

## Acceptance Criteria
- [ ] Each fallback accessor calls `read_all()` at most once per patient session
- [ ] `get_clinical_notes_by_keywords` does not trigger a second `read_all()` when `get_clinical_notes_by_type` has already run
- [ ] `json.loads()` is not called for notes that will be filtered out by type
- [ ] A test confirms the cache hit path does not make additional network calls
- [ ] CaboodleFileAccessor caching behavior is not regressed

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
