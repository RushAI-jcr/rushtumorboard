---
title: "Batch E2E Test Runner & Input Validation for GYN Tumor Board"
problem_type: testing-infrastructure
component: evaluation/testing
symptoms:
  - "No systematic end-to-end testing for 15 real patient cases through 10-agent pipeline"
  - "Clinician input requirements and GUID-to-query mapping undefined"
  - "No artifact validation for Word doc 4-column layout or PPTX 3-slide output"
  - "No disease-aware NCCN citation checking against ICD-10 codes"
  - "Pipeline timeout tuning unknown (120s too short, 300s required)"
root_causes:
  - "Missing batch test harness for full agent workflow"
  - "No input validation layer for patient data completeness"
  - "AAFEE08B patient has only benign D-codes (D21.9, D25.9, D47.3), not malignant C-codes"
  - "Radiology/pathology data often embedded in clinical_notes.csv, not dedicated CSVs"
technologies:
  - asyncio
  - semantic-kernel
  - python-docx
  - python-pptx
  - pytest
  - epic-caboodle-csv
resolution_files:
  - scripts/run_batch_e2e.py
  - src/evaluation/initial_queries_gyn15.csv
  - src/tests/test_local_agents.py
date_solved: "2026-04-02"
severity: high
---

# Batch E2E Test Runner & Input Validation for GYN Tumor Board

## Problem

The 10-agent Semantic Kernel GYN Oncology Tumor Board pipeline had no batch testing infrastructure. All 15 real patient cases were tested manually one at a time. There was no automated batch processing, no per-patient timeout handling, no artifact validation (Word/PPTX output), no disease-aware NCCN citation checking, and no pass/fail summary reporting.

Clinician input requirements were also undefined — specifically, what exactly a clinician types into Teams to trigger a tumor board case.

## Investigation

1. Discovered the existing `ChatSimulator` (`src/evaluation/chat_simulator.py`, 518 lines) already had CSV-driven batch processing, a `ProceedUser` auto-proceed mechanism, and checkpointing — providing a foundation to build on rather than starting from scratch.
2. Analyzed `AppContext`/`ChatContext` requirements for group chat creation to understand the dependency graph.
3. Identified local accessors (`LocalChatArtifactAccessor`, `LocalChatContextAccessor`, etc.) as drop-in replacements for Azure Blob storage, enabling fully local E2E runs.
4. Validated all 15 real patient GUIDs have complete data across 7 CSV types.
5. Discovered patient `AAFEE08B` has only benign D-codes (no malignant C-codes) — the ICD-10 validation needed to accept `D*` codes alongside `C*` codes.
6. Confirmed radiology/pathology data lives in `clinical_notes.csv` via the 3-layer fallback pattern (dedicated report CSV -> filtered clinical notes by NoteType -> keyword-matched clinical notes).
7. Agent detection regex needed the `"agent id: {name}"` format to correctly match agent responses in the group chat transcript.

## Root Cause

Missing batch test harness. The existing `ChatSimulator` had the right primitives (CSV loading, group chat creation, simulated users, checkpointing) but lacked per-patient timeout wrapping, artifact validation, disease-aware NCCN checks, and summary reporting.

## Solution

### File 1: `scripts/run_batch_e2e.py` (~350 lines)

Batch runner orchestrating E2E tests across all 15 patients.

Key functions:

| Function | Purpose |
|----------|---------|
| `create_local_app_context()` | Builds `AppContext` with local accessors + Azure OpenAI |
| `run_single_patient()` | Creates group chat, runs with `ProceedUser`, wraps in `asyncio.wait_for(timeout=300)` |
| `validate_docx()` / `validate_pptx()` | Post-run artifact inspection (4-column Word, 3-slide PPTX) |
| `get_disease_site()` | ICD-10 prefix mapping (C54/C55=uterine, C52=vaginal, C51=vulvar) |
| `extract_nccn_citations()` | Regex extraction for ENDO-/VAG-/VULVA- page codes |
| `print_summary()` / `save_summary_json()` | Console table + JSON report |

CLI flags: `--patients N`, `--timeout SECS`, `--patient-id GUID`, `--print`, `--csv PATH`

### File 2: `src/evaluation/initial_queries_gyn15.csv`

15 rows: `patient_id`, `initial_query` ("Prepare tumor board case for patient {GUID}"), `followup` (empty). Feeds directly into `ChatSimulator.load_initial_queries()`.

### File 3: `tests/test_local_agents.py` Section H — TestInputValidation (152 tests)

| Test | Count | Purpose |
|------|-------|---------|
| `test_load_patient_csv_types` | 105 | 15 GUIDs x 7 CSV types data loading |
| `test_patient_has_icd10_codes` | 15 | ICD-10 present, accepts C* and D* prefixes |
| `test_invalid_guid_handling` | 1 | Graceful error for nonexistent GUID |
| `test_clinical_notes_contain_embedded_reports` | ~31 | 3-layer fallback data exists in clinical_notes.csv |

## Key Code Patterns

**Per-patient timeout:**

```python
try:
    await asyncio.wait_for(
        simulator.chat(patient_id, initial_query, followups, max_turns=30),
        timeout=300  # 5 minutes
    )
    status = "PASS"
except asyncio.TimeoutError:
    status = "TIMEOUT"
except Exception as e:
    status = f"FAIL: {e}"
```

**Disease-aware NCCN validation:**

```python
nccn_covered = any(
    code.startswith(("C54", "C55"))  # uterine
    or code.startswith("C52")        # vaginal
    or code.startswith("C51")        # vulvar
    for code in icd_codes
)
```

**ICD-10 validation accepting benign codes:**

```python
assert any(code.startswith(("C", "D")) for code in icd_codes), \
    f"Patient {pid} has no cancer-related ICD-10 codes"
```

## Errors Encountered and Fixes

| Error | Fix |
|-------|-----|
| 120s per-patient timeout too short; complex cases timed out | Increased default to 300s (5 minutes) |
| Agent detection regex used wrong format, failing to parse agent turns | Fixed to match `"agent id: {name}"` format from readable text |
| AAFEE08B failed ICD-10 assertion (only benign D-codes, no C-codes) | Broadened validation to accept both `C*` and `D*` prefixes |
| logfire ImportError (`_ExtendedAttributes`) when running pytest | Run with `-p no:logfire` to disable the plugin |

## Prevention Strategies

### Timeout Configuration

- **Rule**: Set E2E timeouts to minimum 300s for 10-agent workflows. Scale proportionally if agents increase.
- **Why**: 10 agents x ~30s each + LLM API latency + fallback searches exceeded 120s.
- **How to apply**: Review timeout when adding agents. In CI, use 2x local timeout for shared runner contention.

### Agent Detection Regex

- **Rule**: Validate agent detection patterns against actual rendered output, not assumed formats.
- **Why**: Readable text uses `"agent id: {name}"` format; original regex expected a different pattern.
- **How to apply**: Maintain sample output fixtures. Re-run detection tests when chat formatter changes.

### ICD-10 Code Coverage

- **Rule**: Accept the full ICD-10 spectrum for GYN oncology: `C*`, `D*`, `N*`, `Z*`, `R*`.
- **Why**: AAFEE08B had only D-category codes (benign neoplasms). Single-prefix check incorrectly flagged as missing diagnosis.
- **How to apply**: When adding patients, inspect diagnosis codes and verify the validation whitelist covers all prefixes present.

### Three-Layer Data Fallback

- **Rule**: All data retrieval must implement 3-layer fallback: dedicated CSV -> NoteType-filtered clinical notes -> keyword-matched clinical notes.
- **Why**: Radiology/pathology findings are frequently embedded in clinical_notes.csv, not dedicated report CSVs. Epic Caboodle exports are inconsistent.
- **How to apply**: Test each fallback layer in isolation per agent. When adding patients, document which layers contain each data type.

### Logfire Plugin Exclusion

- **Rule**: Run E2E tests with `-p no:logfire` to prevent `_ExtendedAttributes` ImportError.
- **Why**: logfire pytest plugin imports OpenTelemetry internals incompatible with the test environment.
- **How to apply**: Add to `pyproject.toml` under `[tool.pytest.ini_options]`: `addopts = "-p no:logfire"`. Re-test without exclusion on dependency upgrades.

## Maintenance

### Adding New Patients

1. Inspect data distribution across 7 CSV types and document fallback layers
2. Check ICD-10 codes — update validation whitelist if new prefixes appear
3. Run single-patient first with verbose logging before adding to batch
4. Update patient count in tests and initial_queries CSV

### Quarterly NCCN Refresh

1. Re-run preprocessing pipeline (Docling + PyMuPDF + GPT-4o vision)
2. Run full E2E batch and diff outputs against previous quarter
3. Review changed outputs for clinical coherence vs. extraction artifacts
4. Update assertions if guideline changes alter expected recommendations

### CI Integration

- E2E tests are slow (~5 min/patient). Run nightly or on-demand, not per-commit.
- Fast unit tests (ICD-10 validation, regex, fallback logic) run per-commit.

## Cross-References

- **Plan**: [docs/plans/2026-04-02-feat-clinician-input-audit-batch-e2e-test-runner-plan.md](../../plans/2026-04-02-feat-clinician-input-audit-batch-e2e-test-runner-plan.md) — Full implementation specification
- **Brainstorm**: [docs/brainstorms/2026-04-02-clinician-input-audit-test-strategy-brainstorm.md](../../brainstorms/2026-04-02-clinician-input-audit-test-strategy-brainstorm.md) — Input audit decisions and test strategy
- **NCCN Integration**: [nccn-guidelines-agent-integration.md](nccn-guidelines-agent-integration.md) — NCCN tool used in citation validation
- **Data Fallback**: [../data-issues/multi-layer-fallback-csv-caching-strategy.md](../data-issues/multi-layer-fallback-csv-caching-strategy.md) — 3-layer fallback critical for real patient data
- **ChatSimulator**: `src/evaluation/chat_simulator.py` — Foundation for batch processing
- **Evaluation Guide**: `docs/evaluation.md` — ChatSimulator usage patterns and CSV format
