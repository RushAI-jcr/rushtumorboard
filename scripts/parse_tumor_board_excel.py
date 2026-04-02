#!/usr/bin/env python3
"""
Parse Tumor Board Excel into per-patient CSV folders.

Reads 'Tumor Board Data Apr 1, 2026.xlsx' and creates one folder per PatientID
under infra/patient_data/{patient_id}/ with 7 CSV files matching the Caboodle schema.

Skips existing synthetic patients (patient_gyn_001, patient_gyn_002).
"""

import csv
import datetime
import os
import sys

import openpyxl

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
EXCEL_PATH = os.path.join(os.path.dirname(REPO_ROOT), "Tumor Board Data Apr 1, 2026.xlsx")
OUTPUT_DIR = os.path.join(REPO_ROOT, "infra", "patient_data")

# Synthetic patients to skip (don't overwrite)
SKIP_PATIENTS = {"patient_gyn_001", "patient_gyn_002", "patient_4"}

# Sheet name -> output CSV filename (they already match, but explicit for clarity)
SHEET_MAP = {
    "clinical_notes.csv": "clinical_notes.csv",
    "pathology_reports.csv": "pathology_reports.csv",
    "radiology_reports.csv": "radiology_reports.csv",
    "lab_results.csv": "lab_results.csv",
    "cancer_staging.csv": "cancer_staging.csv",
    "medications.csv": "medications.csv",
    "diagnoses.csv": "diagnoses.csv",
}


def format_value(val):
    """Convert cell value to CSV-safe string."""
    if val is None:
        return ""
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    return str(val)


def find_patient_id_col(headers):
    """Find the index of the PatientID column."""
    for i, h in enumerate(headers):
        if h and "PatientID" in str(h):
            return i
    return None


def parse_sheet(ws):
    """Parse a worksheet into {patient_id: [rows]} grouped by PatientID.

    Returns (headers, patient_rows) where patient_rows is a dict.
    """
    rows_iter = ws.iter_rows(values_only=True)
    headers = list(next(rows_iter))

    pat_col = find_patient_id_col(headers)
    if pat_col is None:
        print(f"  WARNING: No PatientID column found, skipping")
        return headers, {}

    patient_rows = {}
    for row in rows_iter:
        patient_id = row[pat_col]
        if patient_id is None or str(patient_id).strip() == "":
            continue  # skip null rows
        pid = str(patient_id).strip()
        if pid not in patient_rows:
            patient_rows[pid] = []
        patient_rows[pid].append(row)

    return headers, patient_rows


def write_csv(filepath, headers, rows):
    """Write rows to a CSV file with proper formatting."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([format_value(v) for v in row])


def main():
    if not os.path.exists(EXCEL_PATH):
        print(f"ERROR: Excel file not found: {EXCEL_PATH}")
        sys.exit(1)

    print(f"Reading: {EXCEL_PATH}")
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True)
    print(f"Sheets: {wb.sheetnames}")

    # Collect all patient IDs across all sheets
    all_patients = set()
    sheet_data = {}  # {sheet_name: (headers, {pid: [rows]})}

    for sheet_name in wb.sheetnames:
        if sheet_name not in SHEET_MAP:
            print(f"  Skipping unknown sheet: {sheet_name}")
            continue

        print(f"\nParsing sheet: {sheet_name}")
        ws = wb[sheet_name]
        headers, patient_rows = parse_sheet(ws)
        sheet_data[sheet_name] = (headers, patient_rows)

        for pid, rows in patient_rows.items():
            all_patients.add(pid)
            print(f"  {pid}: {len(rows)} rows")

    wb.close()

    # Filter out synthetic patients
    new_patients = sorted(all_patients - SKIP_PATIENTS)
    skipped = all_patients & SKIP_PATIENTS

    print(f"\n{'='*60}")
    print(f"Total unique patients: {len(all_patients)}")
    print(f"New patients to create: {len(new_patients)}")
    if skipped:
        print(f"Skipped (synthetic): {skipped}")
    print(f"{'='*60}")

    # Create folders and write CSVs
    for pid in new_patients:
        patient_dir = os.path.join(OUTPUT_DIR, pid)
        print(f"\nCreating: {patient_dir}/")

        for sheet_name, csv_filename in SHEET_MAP.items():
            if sheet_name not in sheet_data:
                continue
            headers, patient_rows = sheet_data[sheet_name]
            rows = patient_rows.get(pid, [])
            csv_path = os.path.join(patient_dir, csv_filename)
            write_csv(csv_path, headers, rows)
            print(f"  {csv_filename}: {len(rows)} rows")

    print(f"\nDone! Created {len(new_patients)} patient folders in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
