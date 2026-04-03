---
title: "feat: Clinician Input Audit & Batch E2E Test Runner"
type: feat
date: 2026-04-02
brainstorm: docs/brainstorms/2026-04-02-clinician-input-audit-test-strategy-brainstorm.md
---

# Clinician Input Audit & Batch E2E Test Runner

## Overview

Define the minimal clinician input required to trigger a tumor board case (MRN only, GUID = MRN for pilot), then build a batch E2E test runner that processes all 15 real Caboodle patient GUIDs through the full 10-agent workflow and produces a pass/fail report with output artifacts (Word + PPTX).

**Key insight:** The existing `ChatSimulator` (`src/evaluation/chat_simulator.py`) already handles batch patient processing with CSV-driven queries, checkpointing, and simulated user responses. We extend it rather than building from scratch.

## Problem Statement / Motivation

- No systematic way to test the full agent pipeline against real patient data
- Clinician input requirements are undefined (what exactly do they type?)
- No validation that all 15 real cases complete end-to-end without errors
- No artifact validation (Word doc has 4 columns, PPTX has 3 slides)
- Need two-tier review: JCR does technical QA, then GYN oncology attending reviews clinical accuracy

## Proposed Solution

### Part 1: Initial Queries CSV

Create `evaluation/initial_queries_gyn15.csv` with one row per real patient GUID:

```csv
patient_id,initial_query,followup
REDACTED-PATIENT-001,"Prepare tumor board case for patient REDACTED-PATIENT-001",
REDACTED-PATIENT-002,"Prepare tumor board case for patient REDACTED-PATIENT-002",
...
```

This feeds directly into `ChatSimulator.load_initial_queries()`.

### Part 2: Batch Test Runner Script

Create `scripts/run_batch_e2e.py` that:

1. Loads the initial queries CSV
2. Configures `AppContext` with local accessors (no Azure Blob dependency) + Azure OpenAI
3. Creates a `ChatSimulator` with `ProceedUser` (auto-proceeds through 9-step workflow)
4. Wraps each patient in `asyncio.wait_for(timeout=300)` (5-minute hard timeout)
5. After each case, validates:
   - Chat completed (not timed out)
   - All 10 agents spoke at least once
   - ReportCreation generated Word + PPTX artifacts
   - Word doc has 4 populated sections (open with python-docx)
   - PPTX has 3 slides (open with python-pptx)
   - ClinicalGuidelines cited NCCN page codes (for uterine/vaginal/vulvar cases)
6. Produces a summary report (JSON + console table)

### Part 3: Input Validation Tests

Add to `tests/test_local_agents.py`:

- Invalid GUID → graceful error (not stack trace)
- Empty message → Orchestrator asks for patient ID
- Patient with minimal dedicated reports → 3-layer fallback succeeds

## Technical Considerations

### Building on ChatSimulator

The existing `ChatSimulator` (518 lines) already provides:

| Feature | Status | Location |
|---------|--------|----------|
| CSV-driven patient list | Exists | `load_initial_queries()` :251 |
| Group chat creation per patient | Exists | `setup_group_chat()` :236 |
| Simulated user (auto-proceed) | Exists | `ProceedUser` :40 |
| Simulated user (LLM-driven) | Exists | `LLMUser` :67 |
| Checkpointing (resume interrupted runs) | Exists | `_save_checkpoint()` :509 |
| Chat history saving (JSON + readable text) | Exists | `save()` :395 |
| **Per-patient timeout** | **Missing** | Needs `asyncio.wait_for()` in `simulate_chats()` |
| **Artifact validation** | **Missing** | Needs post-chat validation step |
| **Pass/fail summary report** | **Missing** | Needs new reporting layer |
| **NCCN citation check** | **Missing** | Needs ClinicalGuidelines output inspection |

### AppContext Setup for Local Testing

```python
# scripts/run_batch_e2e.py — key setup
app_ctx = AppContext(
    all_agent_configs=load_agent_config("default"),
    data_access=create_local_data_access(data_dir="../infra/patient_data"),
    credential=None,  # Use API key or AzureCliCredential
    cognitive_services_token_provider=token_provider,
)
```

### Timeout Strategy

```python
# Wrap each patient case in asyncio.wait_for
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

### Artifact Validation

After each case, check local output directory for generated files:

```python
# Check Word doc
from docx import Document
doc = Document(docx_path)
tables = doc.tables
assert len(tables) >= 1, "Word doc missing main table"
# Verify 4-column layout has content

# Check PPTX
from pptx import Presentation
pptx = Presentation(pptx_path)
assert len(pptx.slides) == 3, f"Expected 3 slides, got {len(pptx.slides)}"
```

### NCCN Citation Validation (Disease-Aware)

Not all 15 patients will be uterine/vaginal/vulvar. The NCCN tool only covers these. For ovarian/cervical cases, skip NCCN citation check:

```python
# Determine disease site from diagnoses.csv
diagnoses = await caboodle.get_diagnoses(patient_id)
icd_codes = [d.get("ICD10Code", "") for d in diagnoses]

nccn_covered = any(
    code.startswith(("C54", "C55"))  # uterine
    or code.startswith("C52")        # vaginal
    or code.startswith("C51")        # vulvar
    for code in icd_codes
)
```

### Rate Limiting

15 patients x ~30 iterations x 3 LLM calls/iteration = ~1,350 Azure OpenAI calls. With GPT-4.1 at typical RPM limits, may hit 429 errors. Mitigate:

- Run sequentially (not parallel) — ChatSimulator already does this
- Use `ProceedUser` (no LLM calls for user simulation) to reduce call count by ~33%
- Add retry logic with exponential backoff for 429 responses

### LLM Non-Determinism

Even with `temperature=0, seed=42`, agent outputs vary between runs. Accept this:

- Single trial (`trial_count=1`) for Phase 1 "completes without errors" goal
- Structural checks only (artifact exists, sections populated, NCCN codes present)
- Don't assert exact text content

## Acceptance Criteria

### Functional

- [ ] Initial queries CSV exists with all 15 real GUIDs
- [ ] Batch runner script processes all 15 patients sequentially
- [ ] Each case has a 5-minute timeout with graceful handling
- [ ] Pass/fail summary report generated (JSON + console table)
- [ ] Word doc validated: 4-column layout with content
- [ ] PPTX validated: 3 slides present
- [ ] NCCN citations checked for uterine/vaginal/vulvar cases
- [ ] Checkpointing works (can resume interrupted batch)

### Input Validation

- [ ] Invalid GUID returns graceful error message
- [ ] Patient data loading succeeds for all 15 GUIDs (all 7 CSV types)
- [ ] 3-layer fallback tested: patient with minimal pathology_reports.csv still gets pathology from clinical_notes.csv

### Non-Functional

- [ ] Total batch runtime under 75 minutes (15 patients x 5 min max)
- [ ] Script runnable with `python3 scripts/run_batch_e2e.py` from repo root
- [ ] Output artifacts saved to `evaluation/batch_e2e_output/` per patient

## Summary Report Format

```
================================================================================
BATCH E2E TEST REPORT — 2026-04-02 15:30:00
================================================================================

Patient GUID                              Status   Time    Agents  Doc  PPTX  NCCN
──────────────────────────────────────────────────────────────────────────────────
REDACTED-PATIENT-001     PASS     4m12s   10/10   OK   OK    N/A (ovarian)
REDACTED-PATIENT-002     PASS     3m45s   10/10   OK   OK    ENDO-4,ENDO-7
REDACTED-PATIENT-003     FAIL     2m01s   7/10    OK   MISS  —
...
──────────────────────────────────────────────────────────────────────────────────
TOTAL: 13/15 PASS, 1 FAIL, 1 TIMEOUT
```

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `evaluation/initial_queries_gyn15.csv` | Create | 15 rows, one per real GUID |
| `scripts/run_batch_e2e.py` | Create | Batch test runner with timeout + artifact validation |
| `src/tests/test_local_agents.py` | Modify | Add input validation tests (Section H) |
| `src/evaluation/chat_simulator.py` | Modify | Add optional per-chat timeout parameter |

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Rate limiting (429 errors) on 1,350+ API calls | Medium | Sequential processing, ProceedUser, retry with backoff |
| Non-GYN patients in the 15 GUIDs | Likely | Disease-aware NCCN check; skip citation validation for ovarian/cervical |
| 3-layer fallback fails for sparse patient data | Low | Pre-validate all 15 GUIDs have clinical_notes.csv with embedded reports |
| Total runtime exceeds 75 min | Low | ProceedUser reduces turns; early termination if agents complete before max_turns |
| ChatSimulator API changes break integration | Low | Pin Semantic Kernel version; test runner imports directly |

## References

- Brainstorm: `docs/brainstorms/2026-04-02-clinician-input-audit-test-strategy-brainstorm.md`
- ChatSimulator: `src/evaluation/chat_simulator.py`
- Evaluator: `src/evaluation/evaluator.py`
- Local Accessors: `src/tests/local_accessors.py`
- Group Chat: `src/group_chat.py:110-336`
- Content Export: `src/scenarios/default/tools/content_export/content_export.py`
- Presentation Export: `src/scenarios/default/tools/presentation_export.py`
- Data Fallback: `docs/solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md`
- NCCN Integration: `docs/solutions/integration-issues/nccn-guidelines-agent-integration.md`
