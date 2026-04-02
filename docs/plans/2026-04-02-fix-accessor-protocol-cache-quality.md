---
title: "fix: Accessor protocol, cache, and code quality (todos 015-022)"
type: fix
date: 2026-04-02
todos: [015, 016, 017, 018, 019, 020, 021, 022]
---

# fix: Accessor protocol, cache, and code quality (todos 015-022)

## Overview

Eight targeted fixes identified during the code review of the 3-layer fallback refactor.
Four are trivial cleanup (< 10 lines each). Four are small–medium structural improvements.
No logic changes — each fix tightens safety, accuracy, or type-checking for existing behavior.

**Recommended order:** lowest-risk first so each commit leaves the codebase in a better state
even if work stops partway through.

---

## Phase 1 — Trivial / Zero-Risk (P3)

### 022 · `_JSON_FENCE_RE` placement + `_LAYER_DESCRIPTIONS` class constant

**File:** `src/scenarios/default/tools/medical_report_extractor.py`

**What:** Two PEP 8 / code-quality fixes — no logic change.

1. Move `_JSON_FENCE_RE = re.compile(...)` to **after** all import blocks (currently sits between
   stdlib and third-party imports).
2. Extract the inline `data_source_description` dict from `_extract` into a class constant:

```python
# medical_report_extractor.py — after all imports
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

class MedicalReportExtractorBase:
    ...
    _LAYER_DESCRIPTIONS: dict[int, str] = {
        1: "Dedicated report CSV",
        2: "Domain-specific clinical notes (operative/procedure notes)",
        3: "Keyword-matched general clinical notes (progress notes, H&P, consults)",
    }
```

In `_extract`, replace the inline dict `.get(source_layer, "Unknown")` call with:
`findings["data_source_description"] = self._LAYER_DESCRIPTIONS[source_layer]`

Remove the `.get(..., "Unknown")` fallback — `source_layer` can only be 1/2/3 here; a
`KeyError` is the correct signal if that ever breaks.

**Acceptance:**
- [x] `_JSON_FENCE_RE` appears after all imports
- [x] `_LAYER_DESCRIPTIONS` is a class constant; inline dict removed from `_extract`
- [x] No `.get(..., "Unknown")` in `_extract`

---

### 018 · Remove dead `accessor_method` from `OncologicHistoryExtractorPlugin`

**File:** `src/scenarios/default/tools/oncologic_history_extractor.py`

**What:** `OncologicHistoryExtractorPlugin` overrides `_extract` entirely, bypassing the base
class logic. The class attribute `accessor_method = "get_metadata_list"` is therefore never
read at runtime. Remove it to eliminate dead code that implies it does something.

```python
# Remove this line:
accessor_method = "get_metadata_list"  # not used directly; overrides _extract
```

Also remove the inline comment `# not used directly; overrides _extract` since the attribute
itself is gone.

**Acceptance:**
- [x] `accessor_method` attribute removed from `OncologicHistoryExtractorPlugin`
- [x] All tests pass

---

## Phase 2 — Security (P2)

### 016 · `_read_file` file_type allowlist

**File:** `src/data_models/epic/caboodle_file_accessor.py`

**What:** Add a `frozenset` allowlist to guard against cross-patient PHI reads via an adversarial
`file_type` argument. Current `patient_id` path traversal check does not cover paths like
`other_patient_id/lab_results` within the same `data_dir`.

```python
# Module-level constant (after imports):
_VALID_FILE_TYPES: frozenset[str] = frozenset({
    "clinical_notes",
    "pathology_reports",
    "radiology_reports",
    "lab_results",
    "cancer_staging",
    "medications",
    "diagnoses",
})

# Top of _read_file:
async def _read_file(self, patient_id: str, file_type: str) -> list[dict]:
    if file_type not in _VALID_FILE_TYPES:
        raise ValueError(f"Invalid file_type {file_type!r}. Must be one of: {sorted(_VALID_FILE_TYPES)}")
    ...
```

All existing callers pass hardcoded literals that are in the allowlist — no callers need changes.

**Acceptance:**
- [x] `_VALID_FILE_TYPES` frozenset defined at module level
- [x] `_read_file` raises `ValueError` for unlisted file types
- [x] All existing tests pass (all callers use valid types)

---

## Phase 3 — Architecture / Type Safety (P2)

### 015 · Extend `ClinicalNoteAccessorProtocol` to cover GYN-specific methods

**File:** `src/data_models/clinical_note_accessor_protocol.py`

**Context:**  
`ClinicalNoteAccessorProtocol` already declares 6 methods (4 base + `get_clinical_notes_by_type`
+ `get_clinical_notes_by_keywords`). But `get_pathology_reports`, `get_radiology_reports`,
`get_lab_results`, `get_tumor_markers`, `get_cancer_staging`, `get_medications`, and
`get_diagnoses` are not declared — they exist only on `CaboodleFileAccessor` and are gated
via `hasattr()` string literals throughout the codebase.

**Important codebase pattern:** Both existing Protocols (`ClinicalNoteAccessorProtocol`,
`SimulatedUserProtocol`) are plain structural Protocols with NO `@runtime_checkable`. All
optional-method detection uses `hasattr()`. **Continue this pattern** — do not introduce
`isinstance(Protocol)` checks or `@runtime_checkable`.

**FhirClinicalNoteAccessor** implements `get_clinical_notes_by_type` and
`get_clinical_notes_by_keywords`. **FabricClinicalNoteAccessor** implements neither.
Only `CaboodleFileAccessor` implements the report/lab/staging/medication/diagnoses methods.

**What to fix:**

1. Add the missing Caboodle-only methods to `ClinicalNoteAccessorProtocol` for type-checker
   completeness. Mark them with a comment indicating they are optional (Caboodle-only):

```python
# clinical_note_accessor_protocol.py
from collections.abc import Sequence
from typing import Protocol


class ClinicalNoteAccessorProtocol(Protocol):
    # --- Base methods: all accessors ---
    async def get_patients(self) -> list[str]: ...
    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]: ...
    async def read(self, patient_id: str, note_id: str) -> str: ...
    async def read_all(self, patient_id: str) -> list[str]: ...

    # --- Filter methods: Caboodle + FHIR ---
    async def get_clinical_notes_by_type(
        self, patient_id: str, note_types: Sequence[str]
    ) -> list[dict]: ...
    async def get_clinical_notes_by_keywords(
        self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]
    ) -> list[dict]: ...

    # --- Report/lab methods: Caboodle only (gate with hasattr before calling) ---
    async def get_pathology_reports(self, patient_id: str) -> list[dict]: ...
    async def get_radiology_reports(self, patient_id: str) -> list[dict]: ...
    async def get_lab_results(
        self, patient_id: str, component_name: str | None = None
    ) -> list[dict]: ...
    async def get_tumor_markers(
        self, patient_id: str, marker_name: str | None = None
    ) -> list[dict]: ...
    async def get_cancer_staging(self, patient_id: str) -> list[dict]: ...
    async def get_medications(self, patient_id: str) -> list[dict]: ...
    async def get_diagnoses(self, patient_id: str) -> list[dict]: ...
```

2. **Do not change any `hasattr()` call sites.** The `hasattr()` guard is the correct
   runtime pattern for optional Caboodle-only methods. The Protocol extension is purely for
   type-checker completeness — Pyright can now validate spelling and signatures of these
   method names rather than letting string literals silently mismatch.

3. Restore the `hasattr()` guard in `oncologic_history_extractor.py._get_clinical_notes()`
   if the linter removed it (it should be there since Fabric doesn't implement it):

```python
async def _get_clinical_notes(self, patient_id: str) -> list[dict]:
    accessor = self.data_access.clinical_note_accessor
    if hasattr(accessor, "get_clinical_notes_by_type"):
        notes = await accessor.get_clinical_notes_by_type(
            patient_id, list(self._RELEVANT_NOTE_TYPES)
        )
    else:
        all_notes = await accessor.read_all(patient_id)
        notes = [
            json.loads(s) if isinstance(s, str) else s
            for s in all_notes
            if (json.loads(s) if isinstance(s, str) else s)
               .get("NoteType", "").lower() in self._RELEVANT_NOTE_TYPES
        ]
    ...
```

**Acceptance:**
- [x] Protocol declares all Caboodle accessor methods with correct signatures
- [x] All existing `hasattr()` guards remain (no `isinstance(Protocol)` introduced)
- [x] `oncologic_history_extractor._get_clinical_notes` has a `hasattr` guard for FHIR/Fabric safety
- [x] Pyright validates method name spelling at call sites

---

## Phase 4 — Performance (P2)

### 021 · Fix double JSON serialization in `patient_data.py`

**File:** `src/scenarios/default/tools/patient_data.py`

**What:** The Caboodle path for `create_timeline` and `process_prompt` calls
`[json.dumps(r) for r in filtered]` on a `list[dict]`, producing `list[str]`, then calls
`json.dumps(files)` again — double-encoding. LLM receives escaped JSON strings instead of
native JSON objects. Adds ~15–20% token overhead per call.

**Fix in `create_timeline` (~line 157):**

```python
# Before:
filtered = await accessor.get_clinical_notes_by_type(patient_id, TIMELINE_NOTE_TYPES)
files = [json.dumps(r) for r in filtered]

# After:
filtered = await accessor.get_clinical_notes_by_type(patient_id, TIMELINE_NOTE_TYPES)
files = filtered  # list[dict] — serialized once below by json.dumps(files)
```

Apply the same change in `process_prompt` (~line 261) wherever the identical pattern appears.

The legacy `read_all()` path already returns `list[str]` (pre-serialized), so it produces a
JSON array of strings when `json.dumps(files)` is called. That existing behavior is
unchanged. After this fix, the Caboodle path produces a JSON array of objects — cleaner and
consistent with what an LLM expects.

**Acceptance:**
- [x] `[json.dumps(r) for r in filtered]` replaced with `filtered` for the Caboodle path
- [x] Same fix applied to both `create_timeline` and `process_prompt`
- [x] Existing PatientHistory tests pass

---

### 017 · Bounded cache for `CaboodleFileAccessor`

**File:** `src/data_models/epic/caboodle_file_accessor.py`

**What:** `_cache: dict[tuple[str, str], list[dict]]` grows unboundedly. At production scale
(20–30 concurrent gunicorn workers serving tumor board sessions across months), this causes
memory growth that could lead to OOM kills.

**Recommendation:** Use `collections.OrderedDict` with a manual maxsize — no new dependency.

```python
import collections

_CACHE_MAX_ENTRIES = 210  # 30 patients × 7 file types; covers a full busy clinic day

class CaboodleFileAccessor:
    _cache: collections.OrderedDict[tuple[str, str], list[dict]]

    def __init__(self, ...):
        ...
        self._cache = collections.OrderedDict()
```

In `_read_file`, after writing to cache:

```python
self._cache[(patient_id, file_type)] = rows
# Evict oldest entry if over budget
if len(self._cache) > _CACHE_MAX_ENTRIES:
    self._cache.popitem(last=False)  # FIFO eviction
```

`cachetools.LRUCache` (Option B from todo 017) would be cleaner but requires adding a
dependency. Defer that if `cachetools` is added to requirements for another reason.

**Acceptance:**
- [x] Cache evicts entries when it exceeds `_CACHE_MAX_ENTRIES`
- [x] `_CACHE_MAX_ENTRIES` constant is module-level and documented
- [x] Existing tests pass (cache behavior is transparent to callers)

---

## Phase 5 — Clinical Safety / Agent Instructions (P2)

### 020 · Add `data_source_layer` caveat to Pathology and Radiology agents

**File:** `src/scenarios/default/config/agents.yaml`

**What:** The extractor tools inject `data_source_layer` (1/2/3) and `data_source_description`
into every response. Agents have no instructions to surface this to the tumor board. A Layer 3
extraction means findings came from a narrative progress note summary, not a dedicated report
— clinicians need to know this before making treatment decisions.

**Add to Pathology agent instructions** (just before the "Yield the chat back to Orchestrator"
line, ~line 173):

```yaml
          When presenting pathology findings, check the `data_source_layer` field in the
          tool response:
          - Layer 1 (dedicated pathology report CSV): present findings normally.
          - Layer 2 (operative/procedure notes) or Layer 3 (keyword-matched clinical notes):
            include a prominent caveat: "⚠ Pathology findings were extracted from
            [data_source_description], not a dedicated pathology report. Confirm with the
            pathology department before treatment decisions."
          If a `truncation_note` field is present, append it after the findings summary.
```

**Add equivalent to Radiology agent instructions** (~line 224), substituting "imaging findings"
and "radiology department."

**Acceptance:**
- [x] Pathology agent instructions include `data_source_layer` caveat language
- [x] Radiology agent instructions include `data_source_layer` caveat language
- [x] Manually verify: run a Layer 2 or 3 extraction scenario and confirm agent output
  includes the caveat

---

## Phase 6 — Test Quality (P3)

### 019 · E2E test timeout + shared kernel fixture

**File:** `src/tests/test_local_agents.py`

**What:** `TestClinicalGuidelinesE2E` has no asyncio timeout — a stalled Azure call hangs CI
indefinitely. The kernel setup is also duplicated across test methods.

**Add timeout decorator:**

```python
import asyncio

class TestClinicalGuidelinesE2E(unittest.IsolatedAsyncioTestCase):

    @pytest.mark.asyncio(timeout=120)
    async def test_ovarian_cancer_guidelines(self):
        ...
```

Or using `unittest` style:

```python
    async def test_ovarian_cancer_guidelines(self):
        async with asyncio.timeout(120):
            ...
```

**Extract shared kernel setup** into `asyncSetUp` / `asyncTearDown` if the same kernel
initialization appears in multiple test methods:

```python
class TestClinicalGuidelinesE2E(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.kernel, self.credential = await _build_kernel()

    async def asyncTearDown(self):
        if self.credential is not None:
            await self.credential.close()

    async def test_ovarian_cancer_guidelines(self):
        async with asyncio.timeout(120):
            agent = await _build_agent(self.kernel)
            ...
```

**Acceptance:**
- [x] Each E2E test method has a timeout (120 s or configurable)
- [x] `AzureCliCredential` is closed in `asyncTearDown`, not inline in each test
- [x] CI does not hang on Azure network failure

---

## Summary Table

| Todo | Priority | File(s) | Effort | Risk |
|------|----------|---------|--------|------|
| 022 | P3 | medical_report_extractor.py | Tiny (2 edits) | None |
| 018 | P3 | oncologic_history_extractor.py | Tiny (1 line) | None |
| 016 | P2 | caboodle_file_accessor.py | Small (5 lines) | None |
| 015 | P2 | clinical_note_accessor_protocol.py + restore hasattr guard | Small (1-2 files) | Low |
| 021 | P2 | patient_data.py (2 sites) | Small | Low |
| 017 | P2 | caboodle_file_accessor.py | Small | Low |
| 020 | P2 | agents.yaml (2 blocks) | Small | Low (text-only) |
| 019 | P3 | test_local_agents.py | Small | None |

All fixes are non-breaking. Recommended to batch as a single commit:
`fix: accessor protocol, cache eviction, double-serialization, agent safety caveats (015-022)`
