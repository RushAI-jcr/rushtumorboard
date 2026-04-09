---
title: "fix: Resolve data gaps between TB Handout 03.04.2026 and agent-available patient data"
type: fix
date: 2026-04-09
---

# Fix TB Handout 03.04.2026 Data Gaps

## Overview

Audit of the March 4 tumor board handout against patient CSV data in `infra/patient_data/` revealed systemic gaps that prevent the agent from reproducing handout-quality output for most of the 15 cases. Three patients are completely unreachable due to MRN mismatches, 9/15 are missing dedicated pathology CSVs, and demographics are nearly empty across the board.

## Problem Statement

The March 4, 2026 tumor board handout has 15 patients. When the agent processes these patients via CaboodleFileAccessor, it encounters:

1. **3 patients unreachable** — MRN in `patient_demographics.csv` doesn't match the MRN the clinician would type (Pts 1, 3, 13)
2. **9/15 missing `pathology_reports.csv`** — agent falls back to 3-layer note search, producing less structured output
3. **Demographics nearly empty** — 13/15 missing name, 15/15 missing DOB, 12/15 missing sex
4. **Sparse radiology** — 3 patients have zero radiology reports; 3 more have only 1
5. **Missing tumor markers** — Pt 7 (Robison) handout references SCC Ag not in `lab_results.csv`
6. **OSH data absent** — Several patients have outside-hospital imaging the system can't access

### Root Cause Analysis

The Excel parse script (`scripts/parse_tumor_board_excel.py`) correctly splits the Caboodle Excel export into per-patient CSV folders. The gaps are **upstream in Caboodle**, not in parsing:

- **MRN extraction** uses regex on clinical note text (lines 57-61, 129-211). For 3 patients, the most frequent MRN found in notes differs from the Epic-assigned MRN used by clinicians. The script only writes demographics when the file doesn't already exist (line 352), so re-running won't fix stale MRNs.
- **Missing pathology/radiology** — these are genuinely absent from the Caboodle export. The Excel has pathology for only 6/15 patients and radiology for only 12/15.
- **Demographics** — the parse script writes empty Name/DOB/Sex (line 231) because Caboodle export doesn't include a demographics sheet.

## Proposed Solution

Three-phase fix: (1) immediate data corrections, (2) parse script improvements, (3) validation automation.

---

## Phase 1: Immediate Data Corrections (Manual)

**Goal:** All 15 March 4 patients are findable by the agent and have correct MRNs.

### 1a. Fix MRN Mismatches

Update `patient_demographics.csv` for 3 patients:

| Pt | Name | GUID | Current MRN | Correct MRN |
|----|------|------|-------------|-------------|
| 1 | L Pyfer | `65F18369-0936-49A5-87CB-B301B9B15ED0` | 9709498 | 9561436 |
| 3 | S Orbesen | `3BF85DD2-68F9-43A6-A5EE-0DDF61C61948` | 9387725 | 9512306 |
| 13 | M Jensen | `F0B00869-15DF-41E4-9798-AF92E8280CDA` | 0266098 | 9399789 |

**File:** `infra/patient_data/{GUID}/patient_demographics.csv` — update MRN column.

### 1b. Populate Demographics

For all 15 patients, fill in PatientName, DOB, and Sex from the handout + clinical notes:

| Pt | GUID | Name | Age (from handout) | Sex |
|----|------|------|----|-----|
| 1 | 65F18369... | Linda Pyfer | 66 | F |
| 2 | 3DB910C1... | Jocelyn Garcia | 23 | F |
| 3 | 3BF85DD2... | Susan Orbesen | 74 | F |
| 4 | C1653F34... | Cecilia Fonson | 76 | F |
| 5 | 8117F6BC... | Nancy Neal | 51 | F |
| 6 | F3D8876E... | Esmeralda Solarzano Franco | 55 | F |
| 7 | E121E99C... | Michelle Robison | 42 | F |
| 8 | 1B848EEC... | Ellen Aronson | 59 | F |
| 9 | E05E2913... | Rosalva Diaz Sanchez | 58 | F |
| 10 | A6E9C447... | Margarita Aguilar | 67 | F |
| 11 | 09CBE23E... | Alejandra Hernandez Serrano | 31 | F |
| 12 | DF9ED173... | Joanne Gilroy | 62 | F |
| 13 | F0B00869... | Melissa Jensen | 40 | F |
| 14 | 75684C22... | Patricia Castro | 56 | F |
| 15 | 423BF4B8... | Hortencia Espinoza | 47 | F |

**Note:** DOB must be calculated from handout age relative to TB date (2026-03-04). This is approximate — exact DOB should come from Epic if available.

### 1c. Re-parse Excel with Force Demographics

Run `parse_tumor_board_excel.py` against `Tumor Board Data TB Mar 4, 2026.xlsx` to ensure all CSVs are up to date. Then manually patch demographics as above.

```bash
cd rushtumorboard
python3 scripts/parse_tumor_board_excel.py "../Tumor Board Data TB Mar 4, 2026.xlsx"
python3 scripts/validate_patient_csvs.py
```

### Acceptance Criteria — Phase 1

- [ ] All 15 patients resolvable by MRN via `CaboodleFileAccessor.resolve_patient_id()`
- [ ] `patient_demographics.csv` has non-empty PatientName and Sex for all 15
- [ ] `validate_patient_csvs.py` passes for all 15 patients
- [ ] Batch E2E runner (`scripts/run_batch_e2e.py`) completes all 15 without MRN errors

---

## Phase 2: Parse Script Improvements

**Goal:** Prevent MRN mismatches and demographics gaps in future Caboodle imports.

### 2a. Add `--force-demographics` flag to parse script

**File:** `scripts/parse_tumor_board_excel.py`

Currently line 352 skips demographics if the file exists. Add a `--force-demographics` flag to overwrite, and always re-extract MRN even for existing patients.

```python
# Line 352-358: change to
if not os.path.exists(demo_path) or args.force_demographics:
    write_demographics_csv(demo_path, pid, mrn)
```

### 2b. Add MRN cross-validation

After extracting MRNs from note text, cross-validate against:
1. Existing `patient_demographics.csv` (if present) — warn on mismatch
2. A handout-derived MRN mapping file (optional `--mrn-map` CSV arg)

**File:** `scripts/parse_tumor_board_excel.py` — new function `validate_mrn_consistency()`

### 2c. Extract Name/Sex/DOB from clinical notes

Enhance `extract_mrn_from_notes()` to also extract:
- **PatientName** from note headers (pattern: `Patient Name: {name}` or `PATIENT NAME: {LAST}, {FIRST}`)
- **Sex** from note text (GYN onc = almost always Female, but validate)
- **DOB** from note headers (pattern: `DOB: {date}` or `Date of Birth: {date}`)

**File:** `scripts/parse_tumor_board_excel.py` — enhance `write_demographics_csv()` to accept extracted fields.

### 2d. Post-parse validation report

After writing CSVs, automatically run validation and print a gap report showing which patients are missing which CSV types — similar to the audit table above.

### Acceptance Criteria — Phase 2

- [ ] `--force-demographics` flag works and overwrites existing demographics
- [ ] MRN cross-validation prints warnings on mismatch
- [ ] Name extraction works for >80% of patients (those with Rush-formatted notes)
- [ ] Post-parse gap report prints automatically

---

## Phase 3: Automated Data Quality Audit

**Goal:** Before every tumor board, automatically compare agent-available data against the handout to flag gaps.

### 3a. Handout-to-data audit script

New script: `scripts/audit_handout_vs_data.py`

Input: TB Handout `.docx` file
Output: Gap report showing per-patient:
- MRN resolvable? (Y/N)
- Demographics complete? (Name/DOB/Sex)
- Which CSV files exist and row counts
- Pathology data available? (CSV or fallback)
- Radiology data available?
- Tumor markers available?
- Genomics available?

This is essentially a scriptified version of the audit we did manually.

### 3b. Integrate with batch runner

Add a `--pre-audit` flag to `scripts/run_batch_e2e.py` that runs the data audit before processing and skips patients with critical gaps (no MRN match).

### Acceptance Criteria — Phase 3

- [ ] `audit_handout_vs_data.py` produces a readable gap report from any TB handout docx
- [ ] Report correctly identifies MRN mismatches, missing CSVs, empty demographics
- [ ] Batch runner `--pre-audit` skips unreachable patients with clear error message

---

## Data Gap Reality Check

Some gaps are **not fixable** by the agent system:

| Gap | Root Cause | Mitigation |
|-----|-----------|------------|
| Missing pathology CSV (9/15) | Caboodle export doesn't include path reports for all patients | 3-layer fallback extracts from clinical notes (already implemented) |
| OSH imaging (Pts 1, 13) | Outside hospital data not in Epic | Agent notes "OSH data not available" in output |
| SCC Ag for Pt 7 | Not in structured labs | Tumor markers tool falls back to clinical note keyword search |
| Radiology sparse (Pts 1, 3, 13) | Not in Caboodle export | Radiology extractor falls back to clinical notes |

The 3-layer fallback architecture (`docs/solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md`) already handles most of these gracefully. The key wins from this plan are:

1. **MRN fixes** — 3 patients go from 0% to 100% reachable
2. **Demographics** — enables age-aware treatment recommendations (e.g., fertility sparing for Pt 2, 23yo)
3. **Prevention** — future imports won't have stale MRNs or empty demographics

## Excel vs Local Data Consistency Matrix

Data in the March 4 Excel exactly matches what's in local CSV folders — confirming the parse script works correctly. Gaps originate in Caboodle:

```
Patient          labs  stage   dx  meds notes  path  rad  var_d var_i
Pt1  Pyfer         --     2     5    --    42    --    --    --    --
Pt2  Garcia        42     2     4    --    50    --     2    --    --
Pt3  Orbesen       --     2     3     2   139    --    --  1848   297
Pt4  Fonson       129     2     8    20   405     1     2    --    --
Pt5  Neal          42    --     5    --    81     7     2    --    --
Pt6  Solarzano    156     2    12    27   186    --     4    65    25
Pt7  Robison     2023     2    15     1  1023    --     3    24    12
Pt8  Aronson      106     2    35    30   104    10    28    20    --
Pt9  Diaz         127     2     9     6    97    --     1   328   100
Pt10 Aguilar      331     2    28   140   734    --     5    47     4
Pt11 Hernandez    278     2    45    75   288    11     1  1400   100
Pt12 Gilroy       424     2    13    75   473     2     8    33    23
Pt13 Jensen        --    --     3    --    58    --    --    --    --
Pt14 Castro       554     2    21    51   541    --     1    29     8
Pt15 Espinoza     135     2    22    56   159    16     7    72    47
```

`--` = zero rows in both Excel and local CSV (Caboodle gap, not parse gap).

## References

### Internal
- Parse script: `scripts/parse_tumor_board_excel.py` (MRN extraction: lines 57-211, demographics write: lines 224-231, skip-if-exists: line 352)
- Validation script: `scripts/validate_patient_csvs.py`
- CaboodleFileAccessor: `src/data_models/epic/caboodle_file_accessor.py` (MRN resolution: lines 188-211)
- 3-layer fallback solution: `docs/solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md`
- Batch E2E brainstorm: `docs/brainstorms/2026-04-02-clinician-input-audit-test-strategy-brainstorm.md`

### Handout Patients (GUID mapping)
```
Pt1  L Pyfer               65F18369-0936-49A5-87CB-B301B9B15ED0  MRN=9561436
Pt2  J Garcia              3DB910C1-4BD5-42B6-B4B7-6A653106DDC5  MRN=9471525
Pt3  S Orbesen             3BF85DD2-68F9-43A6-A5EE-0DDF61C61948  MRN=9512306
Pt4  C Fonson              C1653F34-74EA-4AA5-B18A-FB2AE443CF0E  MRN=0032388
Pt5  N Neal                8117F6BC-A980-4E18-B238-7B854EBD2AD7  MRN=5662616
Pt6  E Solarzano Franco    F3D8876E-971D-4F8C-8530-F50187821BB7  MRN=7323044
Pt7  M Robison             E121E99C-19D3-40D0-8F15-72C3B181ECBE  MRN=9483530
Pt8  E Aronson             1B848EEC-7313-4945-BC73-549E8F414D37  MRN=5670891
Pt9  R Diaz Sanchez        E05E2913-CAEF-4E48-892C-2477DB3CCCBF  MRN=6008674
Pt10 M Aguilar             A6E9C447-BC8E-4703-9EC9-AD583DEFE53D  MRN=7289424
Pt11 A Hernandez Serrano   09CBE23E-7EAC-420B-9C86-C62558A0AA54  MRN=6037881
Pt12 J Gilroy              DF9ED173-BDB0-47EE-A69E-B64128161063  MRN=9091004
Pt13 M Jensen              F0B00869-15DF-41E4-9798-AF92E8280CDA  MRN=9399789
Pt14 P Castro              75684C22-5EF5-4CB6-847B-881CD854DF1F  MRN=9489535
Pt15 H Espinoza            423BF4B8-A494-4384-8C91-059E50484B2E  MRN=6297902
```
