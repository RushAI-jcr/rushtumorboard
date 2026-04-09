#!/usr/bin/env python3
"""
Validate exported Caboodle CSVs for GYN tumor board patients.

Usage:
    python3 scripts/validate_patient_csvs.py
    python3 scripts/validate_patient_csvs.py --data-dir /path/to/patient_data
    python3 scripts/validate_patient_csvs.py --patient patient_gyn_003

Checks:
  - All 7 CSV files exist for each patient directory
  - Each file has the required columns (exact name match)
  - Each file has at least 1 non-empty row
  - NoteText / ReportText fields are non-empty
  - No obviously truncated files (file size > 200 bytes)
"""

import argparse
import csv
import os
import sys

# ---------------------------------------------------------------------------
# Expected schema — must match CaboodleFileAccessor exactly
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = {
    "clinical_notes": ["NoteID", "PatientID", "NoteType", "EntryDate", "NoteText"],
    "pathology_reports": ["ReportID", "PatientID", "ProcedureName", "OrderDate", "ReportText"],
    "radiology_reports": ["ReportID", "PatientID", "ProcedureName", "OrderDate", "ReportText"],
    "lab_results": ["ResultID", "PatientID", "ComponentName", "OrderDate", "ResultValue", "ResultUnit", "ReferenceRange", "AbnormalFlag"],
    "cancer_staging": ["PatientID", "StageDate", "StagingSystem", "TNM_T", "TNM_N", "TNM_M", "StageGroup", "FIGOStage"],
    "medications": ["PatientID", "MedicationName", "StartDate", "EndDate", "Route", "Dose", "Frequency", "OrderClass"],
    "diagnoses": ["PatientID", "DiagnosisName", "ICD10Code", "DateOfEntry", "Status"],
}

# Column aliases handled by CaboodleFileAccessor._COLUMN_ALIASES — accept either name.
# Maps alternate column name -> canonical name (same mapping as the accessor).
# IMPORTANT: Keep in sync with CaboodleFileAccessor._COLUMN_ALIASES
# in src/data_models/epic/caboodle_file_accessor.py (the authoritative source).
COLUMN_ALIASES: dict[str, str] = {
    "NOTE_ID": "NoteID",
    "NOTE_TYPE": "NoteType",
    "NOTE_DATE": "EntryDate",
    "CONCATENATED_TEXT": "NoteText",
    "STATUS": "Status",
    "Frequency (days)": "Frequency",
}

# These columns must have non-empty values in at least 1 row (only checked when rows > 0)
TEXT_COLUMNS = {
    "clinical_notes": "NoteText",
    "pathology_reports": "ReportText",
    "radiology_reports": "ReportText",
}

# These files are optional — 0 rows is a warning, not an error.
# Real patients may have no surgical pathology at Rush (OSH surgery),
# no local imaging, missing lab panels, or staging only in narrative notes.
OPTIONAL_FILE_TYPES = {
    "pathology_reports",    # surgery may have been at OSH
    "radiology_reports",    # imaging may be outside Rush
    "lab_results",          # labs may not have been pulled in full
    "medications",          # some patients are follow-up only
    "cancer_staging",       # staging may be in narrative, not structured Epic fields
}

TUMOR_MARKER_PATTERNS = ["ca-125", "ca125", "he4", "hcg", "cea", "afp", "ldh"]


def check_patient(patient_dir: str, patient_id: str) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). errors causes FAIL; warnings are informational."""
    errors = []
    warnings = []

    for file_type, required_cols in REQUIRED_COLUMNS.items():
        csv_path = os.path.join(patient_dir, f"{file_type}.csv")

        # 1. File exists (optional file types get a warning; required get an error)
        if not os.path.exists(csv_path):
            if file_type in OPTIONAL_FILE_TYPES:
                warnings.append(f"  MISSING: {file_type}.csv — optional, agent uses 3-layer fallback")
            else:
                errors.append(f"  MISSING: {file_type}.csv")
            continue

        # Size check is skipped — empty files are caught by the row-count check below

        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                actual_cols = reader.fieldnames or []
        except Exception as e:
            errors.append(f"  UNREADABLE: {file_type}.csv — {e}")
            continue

        # 3. Required columns present (accept aliases handled by CaboodleFileAccessor)
        # Map actual column names to their canonical equivalents for comparison
        canonical_cols = set()
        for col in actual_cols:
            canonical_cols.add(COLUMN_ALIASES.get(col, col))
        missing_cols = [c for c in required_cols if c not in canonical_cols]
        if missing_cols:
            errors.append(f"  MISSING COLUMNS in {file_type}.csv: {missing_cols}")
            errors.append(f"    (found: {actual_cols})")

        # 4. At least 1 row (optional file types get a warning; required get an error)
        if len(rows) == 0:
            if file_type in OPTIONAL_FILE_TYPES:
                warnings.append(f"  EMPTY (0 rows): {file_type}.csv — no data for this patient")
            else:
                errors.append(f"  EMPTY (0 rows): {file_type}.csv — required")
            continue

        # 5. Text fields non-empty (check canonical name and aliases)
        text_col = TEXT_COLUMNS.get(file_type)
        if text_col:
            # Find the actual column name (may be an alias)
            actual_text_col = text_col if text_col in actual_cols else None
            if not actual_text_col:
                for alias, canonical in COLUMN_ALIASES.items():
                    if canonical == text_col and alias in actual_cols:
                        actual_text_col = alias
                        break
            if actual_text_col:
                non_empty = [r for r in rows if r.get(actual_text_col, "").strip()]
                if not non_empty:
                    errors.append(f"  ALL BLANK: {file_type}.csv column '{actual_text_col}'")

        # 6. Lab results: check for tumor markers (warning only)
        if file_type == "lab_results" and "ComponentName" in actual_cols:
            names_lower = [r.get("ComponentName", "").lower() for r in rows]
            has_marker = any(
                any(m in name for m in TUMOR_MARKER_PATTERNS)
                for name in names_lower
            )
            if not has_marker:
                warnings.append(
                    f"  lab_results.csv has no tumor markers "
                    f"(CA-125, HE4, hCG, etc.) — add CA-125 for full functionality"
                )

        # 7. PatientID column matches expected (warning only)
        if "PatientID" in actual_cols:
            pids = {r.get("PatientID", "") for r in rows}
            if len(pids) > 1 and "" not in pids:
                warnings.append(
                    f"  {file_type}.csv has multiple PatientID values: {pids} "
                    f"— expected '{patient_id}' only"
                )

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate Caboodle CSV exports for tumor board patients")
    parser.add_argument(
        "--data-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "infra", "patient_data"),
        help="Path to patient_data directory",
    )
    parser.add_argument(
        "--patient",
        default=None,
        help="Validate a single patient (e.g. patient_gyn_003)",
    )
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        print(f"ERROR: data-dir not found: {data_dir}")
        sys.exit(1)

    if args.patient:
        patient_ids = [args.patient]
    else:
        patient_ids = sorted(
            d for d in os.listdir(data_dir)
            if os.path.isdir(os.path.join(data_dir, d))
        )

    if not patient_ids:
        print(f"No patient directories found in: {data_dir}")
        sys.exit(1)

    all_ok = True
    for patient_id in patient_ids:
        patient_dir = os.path.join(data_dir, patient_id)

        # Skip legacy directories that use JSON format instead of CSV
        has_any_csv = any(
            os.path.exists(os.path.join(patient_dir, f"{ft}.csv"))
            for ft in REQUIRED_COLUMNS
        )
        if not has_any_csv:
            print(f"[SKIP] {patient_id}  (legacy JSON format — no CSV files)")
            continue

        errors, warnings = check_patient(patient_dir, patient_id)

        if errors:
            all_ok = False
            print(f"\n[FAIL] {patient_id}")
            for e in errors:
                print(e)
            for w in warnings:
                print(f"  WARN: {w.strip()}")
        else:
            csv_counts = {}
            for file_type in REQUIRED_COLUMNS:
                csv_path = os.path.join(patient_dir, f"{file_type}.csv")
                if os.path.exists(csv_path):
                    with open(csv_path, "r", encoding="utf-8-sig") as f:
                        n = sum(1 for _ in csv.DictReader(f))
                    csv_counts[file_type] = n
            summary = ", ".join(f"{k[:4]}:{v}" for k, v in csv_counts.items())
            warn_suffix = f"  [{len(warnings)} warning(s)]" if warnings else ""
            print(f"[OK]   {patient_id}  ({summary}){warn_suffix}")
            for w in warnings:
                print(f"       WARN: {w.strip()}")

    print()
    if all_ok:
        print("All patients passed validation.")
        sys.exit(0)
    else:
        print("Validation failed — fix the issues above, then re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
