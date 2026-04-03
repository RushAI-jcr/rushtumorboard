---
title: "Multi-Layer Fallback and CSV Caching for GYN Tumor Board Agents"
problem_type: data_access_failure
date: 2026-04-02
severity: critical
symptoms:
  - "Pathology/Radiology agents returning 'No reports found' error for most patients"
  - "12/15 real patients missing pathology_reports.csv"
  - "8/15 real patients missing lab_results.csv"
  - "Redundant I/O: same CSV files read 7x per session across agents"
  - "Layer 3 keyword fallback matching 260-405 notes per patient (~5MB), risking LLM context overflow"
  - "Real patient GUID folders exposed to version control (PHI risk)"
tags:
  - data-access
  - caboodle
  - llm-context
  - caching
  - fallback
  - phi
  - python
  - semantic-kernel
related_files:
  - src/data_models/epic/caboodle_file_accessor.py
  - src/scenarios/default/tools/medical_report_extractor.py
  - src/scenarios/default/tools/pathology_extractor.py
  - src/scenarios/default/tools/radiology_extractor.py
  - src/scenarios/default/tools/tumor_markers.py
  - src/scenarios/default/tools/oncologic_history_extractor.py
  - src/tests/test_local_agents.py
  - .gitignore
---

## Problem Statement

After parsing 15 real patient records from an Excel export into per-patient CSV folders under `infra/patient_data/`, an audit revealed that most patients only have `clinical_notes.csv`. The dedicated `pathology_reports.csv`, `radiology_reports.csv`, and `lab_results.csv` files are often absent because the Epic Caboodle export for many patients contains this information only as embedded text within clinical notes (H&P, Progress Notes, Consultation notes, Operative Reports).

The original `MedicalReportExtractorBase._extract()` called `get_pathology_reports()` → received `[]` → returned a hard JSON error. The existing fallback only triggered if the accessor *lacked* the method entirely; since `CaboodleFileAccessor` always has it (just returning `[]` on missing files), the fallback never fired.

Secondary issues discovered: redundant CSV I/O (same file read ~7x per session), uncontrolled Layer 3 keyword breadth causing context window overflow risk, and real patient GUID folders not gitignored (PHI in version control).

## Root Cause

`medical_report_extractor.py` used a single-layer data strategy: call the dedicated accessor method, return error if empty. Clinical notes were never considered as a fallback data source, even though for transfer patients and many real Caboodle exports, all pathology/radiology information is embedded in physician-authored notes.

## Solution

### 1. Three-Layer Fallback in `MedicalReportExtractorBase`

Added two class-level attributes (`layer2_note_types`, `layer3_note_types`, `layer3_keywords`) that subclasses override as **tuples** (not lists — immutable class-level defaults):

```python
class MedicalReportExtractorBase:
    layer2_note_types: tuple[str, ...] = ()
    layer3_note_types: tuple[str, ...] = ()
    layer3_keywords: tuple[str, ...] = ()
    MAX_REPORTS = 25
    MAX_CHARS_PER_REPORT = 4000
    MAX_TOTAL_CHARS = 80_000  # ~20K tokens
```

The `_extract()` method now:

1. **Layer 1**: Calls `get_pathology_reports()` / `get_radiology_reports()` (current behavior).
2. **Layer 2**: If empty, filters clinical notes by domain-specific NoteTypes via `get_clinical_notes_by_type()`.
3. **Layer 3**: If still empty, filters general notes by keywords via `get_clinical_notes_by_keywords()`.
4. Logs the active layer and caps report count + total chars before sending to LLM.
5. Prepends a layer-specific preamble so the LLM knows the data source quality:
   - Layer 1: `"Extract structured [type] findings from these dedicated [type] reports:"`
   - Layer 2: `"No dedicated [type] reports available. Extract from these procedure/operative notes..."`
   - Layer 3: `"No dedicated [type] reports available. Extract any [type] information from these clinical notes..."`

### 2. Subclass Layer Configurations

**PathologyExtractorPlugin** (`pathology_extractor.py`):
```python
layer2_note_types = ("Operative Report", "Procedures", "Brief Op Note")
layer3_note_types = ("Progress Notes", "H&P", "Consults", "Discharge Summary")
layer3_keywords = (
    "pathology", "histolog", "biopsy", "immunohistochem", "carcinoma",
    "adenocarcinoma", "serous", "endometrioid", "grade", "brca",
    "mmr", "msi", "p53", "er/pr", "her2",
)
```

**RadiologyExtractorPlugin** (`radiology_extractor.py`):
```python
layer2_note_types = ()  # no dedicated radiology note types in this data
layer3_note_types = ("Progress Notes", "H&P", "Consults", "ED Provider Notes", "Discharge Summary")
layer3_keywords = (
    "ct scan", "ct chest", "ct abdomen", "ct pelvis", "ct a/p",
    "mri", "pet", "pet-ct", "pet/ct", "ultrasound", "transvaginal", "tvus",
    "imaging", "radiolog", "recist",
)
```

**Key tuning**: Radiology keywords were deliberately narrowed (removed "mass", "lesion", "findings:", "impression:", "lymphadenopathy", "metast") after Layer 3 matched 81% of all notes (260+ notes per patient) before tuning.

### 3. New `CaboodleFileAccessor` Methods

```python
from collections.abc import Sequence

async def get_clinical_notes_by_type(
    self, patient_id: str, note_types: Sequence[str]
) -> list[dict]:
    notes = await self._read_file(patient_id, "clinical_notes")
    if not note_types:
        return notes
    type_set = {t.lower() for t in note_types}
    return [
        n for n in notes
        if n.get("NoteType", n.get("note_type", "")).lower() in type_set
    ]

async def get_clinical_notes_by_keywords(
    self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]
) -> list[dict]:
    notes = await self.get_clinical_notes_by_type(patient_id, note_types)
    if not keywords:
        return notes
    kw_lower = [k.lower() for k in keywords]
    return [
        n for n in notes
        if any(
            kw in n.get("NoteText", n.get("note_text", n.get("text", ""))).lower()
            for kw in kw_lower
        )
    ]
```

**Type**: `Sequence[str]` (from `collections.abc`) rather than `list[str]` so that both `list` and `tuple` inputs are accepted — essential since subclasses pass `tuple[str, ...]` class attributes.

### 4. Session-Level CSV Cache

Added a dict cache to `CaboodleFileAccessor.__init__`:

```python
self._cache: dict[tuple[str, str], list[dict]] = {}
```

`_read_file()` now checks the cache first and stores on miss:

```python
async def _read_file(self, patient_id: str, file_type: str) -> list[dict]:
    cache_key = (patient_id, file_type)
    if cache_key in self._cache:
        return self._cache[cache_key]
    # ... read CSV/Parquet/legacy JSON ...
    self._cache[cache_key] = rows
    return rows
```

**Why safe**: asyncio is single-threaded (cooperative multitasking); dict `__setitem__` is atomic in CPython; clinical data is immutable within a session. A benign double-read race on the first concurrent access is acceptable — same data, same result.

**Impact**: Eliminates ~7× redundant reads of the same CSV file. For a 15-patient session (~41MB patient data), reduces I/O to ~6MB.

### 5. Volume Caps for LLM Context Safety

`MedicalReportExtractorBase`:
- `MAX_REPORTS = 25` — hard cap on number of reports/notes sent
- `MAX_CHARS_PER_REPORT = 4000` — truncate individual reports with `[...truncated...]`
- `MAX_TOTAL_CHARS = 80_000` — break loop when combined text exceeds ~20K tokens

`OncologicHistoryExtractorPlugin` (separate caps for larger context):
- `MAX_NOTES = 30`
- `MAX_CHARS_PER_NOTE = 4000`
- `MAX_TOTAL_CHARS = 120_000` — ~30K tokens, leaves room for system prompt

### 6. PHI Protection

Added to `.gitignore` at repository root:

```gitignore
# Real patient data (GUID-format folders) — NEVER commit PHI
infra/patient_data/[A-F0-9]*-*-*-*-*/
```

The glob pattern matches UUID-formatted folder names (e.g., `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`) while preserving synthetic test patients (`patient_gyn_001`, `patient_gyn_002`, `patient_4`).

### 7. Type Safety Fixes

- `list[str] = []` class-level defaults → `tuple[str, ...] = ()` (immutable, prevents shared mutable state between instances)
- `_get_marker_notes_fallback` return type: `-> str | None`
- `_doubling_time` return type: `-> float | None`
- All `logger.info(f"...")` → `logger.info("%s", ...)` (lazy formatting, per PEP best practice)
- Removed unused `values` variable in `_analyze_trend` and `dates` variable in `get_all_tumor_markers`
- Simplified O(n²) keyword dedup in `TumorMarkerPlugin` to `[marker.lower()] + list(self._MARKER_KEYWORDS)`

## Verification

1. Run `pytest tests/test_local_agents.py -v` — all tests pass including 5 new tests:
   - `test_get_clinical_notes_by_type`
   - `test_get_clinical_notes_by_type_empty`
   - `test_get_clinical_notes_by_keywords`
   - `test_get_clinical_notes_by_keywords_no_match`
   - `test_file_caching` (verifies `notes1 is notes2` — same object reference)

2. Confirm `git status` shows no real patient GUID folders tracked.

3. For a patient missing `pathology_reports.csv` but with H&P/Progress Notes, confirm the pathology extractor returns structured findings from Layer 2/3 with the appropriate LLM preamble.

## Prevention

**For new extractors**:
1. Always define `layer2_note_types`, `layer3_note_types`, `layer3_keywords` as tuples
2. Validate keyword breadth before deploying: `grep -c` each keyword against `clinical_notes.csv` to estimate match rate — if >30% of notes match, narrow the keywords
3. Volume caps are required — never send unbounded note text to the LLM

**Observability**:
- Layer fallback is logged at `INFO` level: `"Layer 2 fallback: found %d %s-relevant notes (types: %s) for patient %s"`
- Volume cap truncation is logged: `"Hit total char cap (%d) for %s extraction, patient %s — using %d of %d reports"`
- Monitor these log lines in production to detect when Layer 1 data is missing and fallback is firing

**Data hygiene**:
- All new patient data directories must use UUID format so the `.gitignore` pattern catches them automatically
- Synthetic test patients use `patient_gyn_NNN` naming to remain unaffected

## Related

- [GYN Tumor Board Adaptation](../integration-issues/gyn-tumor-board-adaptation.md)
- `docs/data_access.md` — CaboodleFileAccessor architecture overview
- `docs/agent_development.md` — Adding new tools/plugins
- Plan: `docs/plans/2026-03-12-001-layered-data-fallback-for-tumor-board-agents.md`
