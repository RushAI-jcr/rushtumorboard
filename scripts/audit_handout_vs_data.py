#!/usr/bin/env python3
"""
Audit a Tumor Board Handout (.docx) against agent-available patient CSV data.

Usage:
    python3 scripts/audit_handout_vs_data.py "TB Handout 03.04.2026.docx"
    python3 scripts/audit_handout_vs_data.py --data-dir /path/to/patient_data handout.docx

Reads the handout to extract patient names, MRNs, and referenced data elements,
then cross-references against the CSV files in infra/patient_data/ to produce a
gap report showing what the agent can and cannot access.
"""

import argparse
import csv
import os
import re
import sys

# Optional: python-docx for reading .docx files
try:
    from docx import Document  # type: ignore[import-untyped]
    HAS_DOCX = True
except ImportError:
    Document = None  # type: ignore[assignment,misc]
    HAS_DOCX = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_DATA_DIR = os.path.join(REPO_ROOT, "infra", "patient_data")

# CSV file types the agent uses
CSV_TYPES = [
    "clinical_notes", "pathology_reports", "radiology_reports",
    "lab_results", "cancer_staging", "medications", "diagnoses",
    "variant_details", "variant_interpretation",
]

TUMOR_MARKER_NAMES = frozenset([
    "ca-125", "ca125", "ca 125", "he4", "he 4",
    "hcg", "beta-hcg", "beta hcg", "quant b-hcg",
    "cea", "afp", "alpha fetoprotein", "ldh",
    "scc", "scc ag", "squamous cell carcinoma antigen", "inhibin",
])


def extract_patients_from_docx(docx_path):
    """Extract patient info from a tumor board handout .docx.

    Returns list of dicts: {num, name, mrn, age, diagnosis, discussion}.
    """
    if not HAS_DOCX:
        print("ERROR: python-docx is required. Install with: pip install python-docx")
        sys.exit(1)

    doc = Document(docx_path)  # type: ignore[misc]
    patients = []

    for ti, table in enumerate(doc.tables):
        if ti == 0:
            # Table 0 is the header with protocols + column labels + first patient
            # Patient data starts at row 2 (0-indexed)
            if len(table.rows) > 2:
                row = table.rows[2]
                patient = _parse_patient_row(row, len(patients) + 1)
                if patient:
                    patients.append(patient)
        else:
            # Subsequent tables each have 1 row = 1 patient
            if table.rows:
                row = table.rows[0]
                patient = _parse_patient_row(row, len(patients) + 1)
                if patient:
                    patients.append(patient)

    return patients


def _parse_patient_row(row, num):
    """Parse a table row into patient info dict."""
    cells = [cell.text.strip() for cell in row.cells]
    if len(cells) < 2:
        return None

    cell0 = cells[0]

    # Extract MRN (7-digit number on its own line)
    mrn_match = re.search(r"\b(\d{7})\b", cell0)
    mrn = mrn_match.group(1) if mrn_match else ""

    # Extract name (first line, before MRN)
    lines = cell0.split("\n")
    name_line = lines[0].strip() if lines else ""
    # Remove leading number + dot
    name_line = re.sub(r"^\d+\.\s*", "", name_line).strip()

    # Extract age from diagnosis column
    diag_text = cells[1] if len(cells) > 1 else ""
    age_match = re.search(r"(\d{2,3})\s*(?:yo|y/o|year)", diag_text)
    age = int(age_match.group(1)) if age_match else None

    return {
        "num": num,
        "name": name_line,
        "mrn": mrn,
        "age": age,
        "diagnosis": diag_text[:200],
        "history": cells[2][:200] if len(cells) > 2 else "",
        "imaging": cells[3][:200] if len(cells) > 3 else "",
        "discussion": cells[4][:200] if len(cells) > 4 else "",
    }


def build_mrn_index(data_dir):
    """Build MRN -> folder GUID mapping from patient_demographics.csv files."""
    index = {}
    if not os.path.isdir(data_dir):
        return index
    for folder in os.listdir(data_dir):
        demo_path = os.path.join(data_dir, folder, "patient_demographics.csv")
        if not os.path.isfile(demo_path):
            continue
        try:
            with open(demo_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mrn = row.get("MRN", "").strip()
                    name = row.get("PatientName", "").strip()
                    dob = row.get("DOB", "").strip()
                    sex = row.get("Sex", "").strip()
                    if mrn:
                        index[mrn] = {
                            "folder": folder,
                            "name": name,
                            "dob": dob,
                            "sex": sex,
                        }
        except Exception:
            pass
    return index


def audit_patient(patient, data_dir, mrn_index):
    """Audit a single patient's data availability.

    Returns dict with audit results.
    """
    mrn = patient["mrn"]
    result = {
        "num": patient["num"],
        "name": patient["name"],
        "mrn": mrn,
        "age": patient["age"],
        "mrn_resolved": False,
        "folder": None,
        "demographics_complete": False,
        "csv_counts": {},
        "has_pathology": False,
        "has_radiology": False,
        "has_tumor_markers": False,
        "has_genomics": False,
        "pathology_source": "none",
        "issues": [],
        "warnings": [],
    }

    # MRN resolution
    mrn_info = mrn_index.get(mrn)
    if not mrn_info:
        result["issues"].append(f"MRN {mrn} not found in any patient_demographics.csv")
        return result

    result["mrn_resolved"] = True
    result["folder"] = mrn_info["folder"]
    patient_dir = os.path.join(data_dir, mrn_info["folder"])

    # Demographics check
    has_name = bool(mrn_info.get("name"))
    has_dob = bool(mrn_info.get("dob"))
    has_sex = bool(mrn_info.get("sex"))
    result["demographics_complete"] = has_name and has_dob and has_sex
    if not has_name:
        result["warnings"].append("Missing PatientName in demographics")
    if not has_dob:
        result["warnings"].append("Missing DOB in demographics")
    if not has_sex:
        result["warnings"].append("Missing Sex in demographics")

    # CSV file inventory
    for csv_type in CSV_TYPES:
        csv_path = os.path.join(patient_dir, f"{csv_type}.csv")
        if os.path.isfile(csv_path):
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                count = sum(1 for _ in csv.DictReader(f))
            result["csv_counts"][csv_type] = count
        else:
            result["csv_counts"][csv_type] = -1

    # Pathology check
    path_count = result["csv_counts"].get("pathology_reports", -1)
    if path_count > 0:
        result["has_pathology"] = True
        result["pathology_source"] = "pathology_reports.csv"
    else:
        # Check if pathology data exists in clinical notes (3-layer fallback)
        notes_count = result["csv_counts"].get("clinical_notes", -1)
        if notes_count > 0:
            notes_path = os.path.join(patient_dir, "clinical_notes.csv")
            with open(notes_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    text = row.get("NoteText", row.get("CONCATENATED_TEXT", ""))[:500].lower()
                    if any(kw in text for kw in ["patholog", "histol", "carcinoma", "adenocarcinoma", "biopsy result"]):
                        result["has_pathology"] = True
                        result["pathology_source"] = "clinical_notes (fallback)"
                        break
        if not result["has_pathology"]:
            result["issues"].append("No pathology data (neither CSV nor clinical notes)")

    # Radiology check
    rad_count = result["csv_counts"].get("radiology_reports", -1)
    result["has_radiology"] = rad_count > 0

    # Tumor markers check
    lab_count = result["csv_counts"].get("lab_results", -1)
    if lab_count > 0:
        labs_path = os.path.join(patient_dir, "lab_results.csv")
        with open(labs_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                comp = row.get("ComponentName", row.get("component_name", "")).lower()
                if any(m in comp for m in TUMOR_MARKER_NAMES):
                    result["has_tumor_markers"] = True
                    break

    # Genomics check
    var_count = result["csv_counts"].get("variant_details", -1)
    result["has_genomics"] = var_count > 0

    return result


def print_audit_report(results, data_dir):
    """Print formatted audit report."""
    total = len(results)
    resolved = sum(1 for r in results if r["mrn_resolved"])
    demo_complete = sum(1 for r in results if r["demographics_complete"])

    print(f"\n{'='*90}")
    print(f"TUMOR BOARD HANDOUT AUDIT REPORT")
    print(f"{'='*90}")
    print(f"Patients in handout: {total}")
    print(f"MRN resolved:        {resolved}/{total} {'OK' if resolved == total else 'ISSUES'}")
    print(f"Demographics complete:{demo_complete}/{total}")
    print(f"Data directory:      {data_dir}")

    # Summary table
    print(f"\n{'Pt':>3s} {'Name':<22s} {'MRN':>8s} {'Resolved':>9s} {'Notes':>6s} {'Path':>5s} {'Rad':>5s} {'Labs':>5s} {'Meds':>5s} {'Genomics':>9s} {'Markers':>8s}")
    print("-" * 90)

    for r in results:
        def fmt(key):
            c = r["csv_counts"].get(key, -1)
            return "--" if c < 0 else str(c)

        resolved_str = "YES" if r["mrn_resolved"] else "NO"
        markers_str = "YES" if r["has_tumor_markers"] else "--"
        genomics_str = "YES" if r["has_genomics"] else "--"

        print(
            f"{r['num']:>3d} {r['name'][:22]:<22s} {r['mrn']:>8s} "
            f"{resolved_str:>9s} "
            f"{fmt('clinical_notes'):>6s} "
            f"{fmt('pathology_reports'):>5s} "
            f"{fmt('radiology_reports'):>5s} "
            f"{fmt('lab_results'):>5s} "
            f"{fmt('medications'):>5s} "
            f"{genomics_str:>9s} "
            f"{markers_str:>8s}"
        )

    # Issues detail
    any_issues = any(r["issues"] for r in results)
    any_warnings = any(r["warnings"] for r in results)

    if any_issues:
        print(f"\n{'='*90}")
        print("CRITICAL ISSUES (agent cannot produce handout-quality output)")
        print(f"{'='*90}")
        for r in results:
            if r["issues"]:
                print(f"\n  Pt {r['num']} {r['name']} (MRN {r['mrn']}):")
                for issue in r["issues"]:
                    print(f"    - {issue}")

    if any_warnings:
        print(f"\n{'='*90}")
        print("WARNINGS (degraded output quality)")
        print(f"{'='*90}")
        for r in results:
            if r["warnings"]:
                print(f"\n  Pt {r['num']} {r['name']} (MRN {r['mrn']}):")
                for w in r["warnings"]:
                    print(f"    - {w}")

    # Systemic summary
    print(f"\n{'='*90}")
    print("SYSTEMIC GAPS")
    print(f"{'='*90}")
    unreachable = [r for r in results if not r["mrn_resolved"]]
    no_path = [r for r in results if r["mrn_resolved"] and not r["has_pathology"]]
    no_rad = [r for r in results if r["mrn_resolved"] and not r["has_radiology"]]
    no_markers = [r for r in results if r["mrn_resolved"] and not r["has_tumor_markers"]]
    no_genomics = [r for r in results if r["mrn_resolved"] and not r["has_genomics"]]
    incomplete_demo = [r for r in results if r["mrn_resolved"] and not r["demographics_complete"]]

    if unreachable:
        print(f"  UNREACHABLE by agent (MRN mismatch): {len(unreachable)} patients")
        for r in unreachable:
            print(f"    - Pt {r['num']} {r['name']} MRN={r['mrn']}")
    if no_path:
        print(f"  Missing pathology data: {len(no_path)} patients")
    if no_rad:
        print(f"  Missing radiology reports: {len(no_rad)} patients")
    if no_markers:
        print(f"  Missing tumor markers: {len(no_markers)} patients")
    if no_genomics:
        print(f"  Missing genomics data: {len(no_genomics)} patients")
    if incomplete_demo:
        print(f"  Incomplete demographics: {len(incomplete_demo)} patients")

    if not (unreachable or no_path or no_rad):
        print("  No critical systemic gaps detected.")

    return len(unreachable)


def main():
    parser = argparse.ArgumentParser(
        description="Audit TB Handout against agent-available patient data."
    )
    parser.add_argument(
        "docx_path",
        help="Path to the Tumor Board Handout .docx file."
    )
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR,
        help=f"Path to patient data directory (default: {DEFAULT_DATA_DIR})"
    )
    args = parser.parse_args()

    if not os.path.isfile(args.docx_path):
        print(f"ERROR: File not found: {args.docx_path}")
        sys.exit(1)

    print(f"Reading handout: {args.docx_path}")
    patients = extract_patients_from_docx(args.docx_path)
    print(f"Found {len(patients)} patients in handout")

    print(f"\nBuilding MRN index from {args.data_dir}...")
    mrn_index = build_mrn_index(args.data_dir)
    print(f"Found {len(mrn_index)} MRN entries")

    results = []
    for patient in patients:
        result = audit_patient(patient, args.data_dir, mrn_index)
        results.append(result)

    unreachable_count = print_audit_report(results, args.data_dir)

    sys.exit(1 if unreachable_count > 0 else 0)


if __name__ == "__main__":
    main()
