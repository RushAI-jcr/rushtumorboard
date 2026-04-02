# Clinician Input Audit & Test Strategy

**Date:** 2026-04-02
**Status:** Final
**Author:** JCR + Claude

## What We're Building

Two things:

1. **Input audit** — Define and validate the minimal data a clinician must type into Teams to trigger a full tumor board case preparation
2. **Test strategy** — A batch test runner that processes all 15 real Caboodle patient GUIDs end-to-end and produces a pass/fail report with output artifacts

## Why This Approach

### Input: MRN-only (GUID as MRN for pilot)

- Clinician types a single identifier into Teams — nothing else
- For the pilot, the Caboodle GUID *is* the MRN (e.g., `1FEF094B-CAEA-4961-A0AD-65FD3E68AFD5`)
- System extracts everything from Epic Caboodle CSVs automatically
- No clinical question, no context override, no structured fields — the agents handle all extraction
- Production MRN→GUID resolver deferred to post-pilot

**Current flow:**
```
Clinician types MRN/GUID in Teams
  → Teams bot receives message
  → Orchestrator agent starts 9-step workflow
  → PatientHistory calls load_patient_data(patient_id)
  → Each agent processes data in turn
  → ReportCreation generates Word doc + PPTX
```

**What the clinician sees:**
```
Clinician: "1FEF094B-CAEA-4961-A0AD-65FD3E68AFD5"
[System processes for ~3-5 minutes]
[Agents stream status updates in chat]
[Final output: Word doc + PPTX download links]
```

### Testing: Batch Runner Across 15 Real Cases

- Two-tier review: JCR does technical QA first, then GYN oncology attending reviews clinical accuracy
- Success criteria (Phase 1): All 15 cases complete end-to-end without errors, producing Word doc + PPTX with no missing sections
- Success criteria (Phase 2, future): Clinician agrees output is clinically reasonable for >80% of cases

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Clinician input | MRN only (single identifier) | Minimal friction; agents extract everything from Epic data |
| Patient ID for pilot | Caboodle GUID = MRN | Avoids building MRN resolver before pilot; GUIDs already map to patient data folders |
| Test corpus | 15 real patient GUIDs in `infra/patient_data/` | Representative of actual Rush GYN tumor board cases |
| Test runner | Batch script that runs all 15 cases and reports pass/fail | Catches regressions, generates artifacts for clinical review |
| Deployment | Teams (primary) + React demo client (testing) | Clinicians use Teams; developers test via web UI |
| Review process | Technical QA (JCR) → Clinical review (attending) | Two-tier ensures both system stability and clinical accuracy |
| Success bar | Completes without errors (Phase 1) | Low bar to start — clinical accuracy review is Phase 2 |

## Input Audit Checklist

What the system needs to handle when a clinician types a patient identifier:

### Happy Path
- [ ] Clinician types valid GUID → system loads all 7 CSV types → full workflow completes
- [ ] Each agent produces non-empty output
- [ ] Word doc has all 4 columns populated (Diagnosis, Tx History, Imaging, Discussion)
- [ ] PPTX has 3 slides with relevant content
- [ ] ClinicalGuidelines agent cites NCCN page codes (for uterine/vaginal/vulvar cases)
- [ ] ClinicalTrials agent returns relevant trial results

### Edge Cases
- [ ] Invalid/nonexistent GUID → graceful error message (not a stack trace)
- [ ] Patient with minimal data (e.g., only diagnoses.csv populated, missing pathology) → agents handle missing data gracefully, state "Need:" for missing items
- [ ] Patient with non-GYN cancer type → system identifies this and responds appropriately
- [ ] Empty message or non-identifier text → Orchestrator asks for patient ID
- [ ] Multiple patients in one session → system handles sequential case preparation

### Data Completeness per CSV Type
- [ ] `clinical_notes.csv` — at least 1 note present
- [ ] `pathology_reports.csv` — at least 1 report present
- [ ] `radiology_reports.csv` — at least 1 report present
- [ ] `lab_results.csv` — tumor markers (CA-125/HE4) present
- [ ] `cancer_staging.csv` — FIGO stage present
- [ ] `medications.csv` — current medications listed
- [ ] `diagnoses.csv` — primary cancer diagnosis with ICD-10 code

## Test Strategy

### Layer 1: Data Loading (Existing)
Already covered by `TestSyntheticData` and `TestCaboodleGynMethods` in `test_local_agents.py`. Validates CSV parsing and accessor methods.

### Layer 2: Agent Plugin Tests (Existing)
Already covered by `TestNCCNGuidelines` (11 tests) and individual plugin tests. Validates tool functionality in isolation.

### Layer 3: Batch E2E Runner (NEW — to build)
A script that:
1. Iterates over all 15 real patient GUIDs
2. For each patient, runs the full group chat workflow (or a targeted subset of agents)
3. Captures: agent outputs, tool calls made, errors/warnings, execution time
4. Generates artifacts: Word doc + PPTX per patient
5. Produces a summary report:

```
Patient GUID                              | Status  | Time  | Agents OK | Artifacts | Notes
------------------------------------------|---------|-------|-----------|-----------|------
1FEF094B-CAEA-4961-A0AD-65FD3E68AFD5     | PASS    | 4m12s | 10/10     | Doc+PPTX  |
4D5B4EE8-B392-410F-B221-6AC38C94FCE8     | PASS    | 3m45s | 10/10     | Doc+PPTX  |
8048FA31-B2AB-4928-A341-3D00679F368A     | FAIL    | 2m01s | 7/10      | Doc only  | Radiology agent error
...
```

### Layer 4: Clinical Review (Manual)
After Layer 3 passes, the generated Word docs and PPTXs are reviewed by a GYN oncology attending for clinical accuracy. Feedback captured in a structured form.

## Resolved Questions

1. **Data completeness of real GUIDs** — All 15 patient folders are populated with all 7 CSV types. No backfill needed.

2. **Error handling / data fallback** — Radiology and pathology data may live in `clinical_notes.csv`, not just dedicated report CSVs. The 3-layer fallback (dedicated reports -> procedure notes -> general clinical notes) is critical for real patients. Test plan must verify extractors fall back correctly.

3. **Timeout** — 5 minutes per case is acceptable. Current ~3-5 min fits within this budget.

4. **Concurrency** — One patient at a time. Single patient per conversation; start a new chat for next patient. No batch mode needed for pilot.
