---
status: pending
priority: p2
issue_id: "235"
tags: [code-review, security, hipaa]
dependencies: []
---

# parse_tumor_board_excel.py Prints PHI to Console

## Problem Statement

`parse_tumor_board_excel.py` uses `print()` to output raw MRNs, patient names, and dates of birth to stdout. If the script runs in a CI/CD pipeline, screen-sharing session, or stdout is redirected to a log file, PHI is exposed outside the controlled data environment. The MRN mismatch warning prints two different MRN values per patient.

## Findings

**Flagged by:** Security Sentinel (MEDIUM)

**File:** `scripts/parse_tumor_board_excel.py`

Lines printing PHI:
- Line ~316: MRN mismatch warnings with full MRN values
- Line ~470: `print(f"  {pid} -> {mrn}")`
- Line ~484: `print(f"  {pid} -> Name={name}, DOB={dob}, Sex={sex}")`
- Line ~537: `print(f"  patient_demographics.csv: {action_word} MRN={mrn_display}, Name={name_display}")`

## Proposed Solutions

### Option A: Mask by default, --verbose for full output (Recommended)
- Default output masks MRNs (`***{mrn[-4:]}`) and names (`{first_initial}. {last}`)
- `--verbose` flag enables full PHI output with a banner warning
- Effort: Small | Risk: None

### Option B: Add banner warning only
- Print `"WARNING: Output below contains PHI — do not share"` at start
- Effort: Tiny | Risk: Low — still prints PHI, just with a warning

## Acceptance Criteria

- [ ] Default output does not contain full MRNs or patient names
- [ ] Full output available via --verbose flag
- [ ] Banner warning when --verbose is used

## Work Log

- 2026-04-09: Created from code review (Security Sentinel)
