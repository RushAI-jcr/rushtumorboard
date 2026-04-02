# Test Patient Data — GYN Oncology

This directory contains synthetic sample data for testing. Real patient data (GUID-named folders) may exist **locally** but are always gitignored — they are never committed to version control. See `.gitignore` for the exclusion pattern.

## Available Patient Data

| Patient ID | Description |
|-----------|-------------|
| `patient_gyn_001` | Synthetic GYN oncology case for tumor board testing |
| `patient_gyn_002` | Synthetic GYN oncology case for tumor board testing |
| `patient_4` | Legacy test patient (generic cancer case) |

> [!IMPORTANT]
> Do not add real patient data to this directory. For instructions on adding new test data, see the [Data Ingestion Guide](../../docs/data_ingestion.md).

> [!WARNING]
> Real patient folders use UUID format (`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`) and are excluded from git by `.gitignore`. After a fresh clone, no GUID folders should be present. Run `git status` to verify nothing is tracked. If any appear tracked, run `git rm --cached -r infra/patient_data/` to untrack them.
