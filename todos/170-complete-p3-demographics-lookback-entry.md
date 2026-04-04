---
status: pending
priority: p3
issue_id: "170"
tags: [code-review, architecture, documentation]
dependencies: []
---

# Add Explicit _DEFAULT_LOOKBACK Entry for patient_demographics

## Problem Statement

`patient_demographics` is in `_VALID_FILE_TYPES` but not in `_DEFAULT_LOOKBACK` or `_DATE_COLUMNS`. The date filter is a no-op (returns all rows) because `dict.get()` returns `None` for missing keys. This is correct behavior but implicit — a future maintainer changing the fallback could inadvertently filter demographics.

## Findings

- **Source**: Architecture Strategist (LOW), Security Sentinel (LOW)
- **File**: `src/data_models/epic/caboodle_file_accessor.py`

## Proposed Solutions

Add `"patient_demographics": None` to `_DEFAULT_LOOKBACK` dict. One line, documents the design decision.

## Acceptance Criteria

- [ ] `patient_demographics` has explicit `None` entry in `_DEFAULT_LOOKBACK`

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | Architecture Strategist + Security Sentinel both noted implicit behavior |
