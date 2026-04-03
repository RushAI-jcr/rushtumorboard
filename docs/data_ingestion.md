# Data Ingestion

Patient data is stored as Epic Caboodle CSV exports under `infra/patient_data/`. For Azure deployments, data is uploaded to Azure Blob Storage. The system also supports FHIR and Fabric data sources.

> [!CAUTION]
> The Rush GYN Oncology Tumor Board framework is not meant for processing identifiable health records. Ensure that you follow all PHI/PII regulations when configuring or using the system.

## Add Your Own Data

> [!WARNING]
> Data will be publicly available unless you configure authentication as mentioned in [Infrastructure](./infra.md#security)

### Option A: Epic Caboodle CSV Format (Recommended)

This is the primary data format, matching Rush's Epic Clarity/Caboodle exports.

1. **Create a New Folder**:
    - Navigate to `infra/patient_data`.
    - Create a new folder named after the patient (e.g., `patient_gyn_003`).

2. **Add CSV Files**:
    Place the following CSV files in the patient folder:

    | File | Required | Description |
    |------|----------|-------------|
    | `clinical_notes.csv` | Yes | All clinical note types (H&P, consults, telephone encounters, etc.) |
    | `lab_results.csv` | Yes | Lab results with values, units, reference ranges, and dates |
    | `pathology_reports.csv` | Recommended | Surgical pathology and cytology report text |
    | `radiology_reports.csv` | Recommended | Structured radiology report text |
    | `cancer_staging.csv` | Optional | FIGO staging data |
    | `medications.csv` | Optional | Medication history |
    | `diagnoses.csv` | Optional | Diagnosis records |

    Use `scripts/validate_patient_csvs.py` to validate CSV file integrity:
    ```bash
    python scripts/validate_patient_csvs.py infra/patient_data/patient_gyn_003
    ```

    Use `scripts/parse_tumor_board_excel.py` to convert tumor board Excel input into the CSV format:
    ```bash
    python scripts/parse_tumor_board_excel.py <input_excel> <output_patient_folder>
    ```

3. **Add Images** (optional):
    - Create an `images` subfolder and add PNG image files.
    - Create a `metadata.json` file describing the images.

### Option B: Legacy JSON Format

For backward compatibility with the upstream `healthcare-agent-orchestrator`, clinical notes can also be stored as JSON files in a `clinical_notes` subfolder. Each JSON file must contain: `id`, `date`, `type`, and `text` fields.

## Upload Patient Data

- From the command line, run `scripts/uploadPatientData.ps1` (Windows) or `scripts/uploadPatientData.sh` (Linux/Mac) to upload patient data to Azure Blob Storage.
- Alternatively, `azd up` or `azd provision` will upload patient data automatically via the `postprovision` hook.

## Test New Patient Data

From Teams or the React chat UI, test using the new patient ID:

- **Full tumor board review**: `@Orchestrator prepare tumor board for patient id <new_patient_id>`
- **Timeline only**: `@PatientHistory create patient timeline for patient id <new_patient_id>`
- **Validate CSV integrity**: `python scripts/validate_patient_csvs.py infra/patient_data/<new_patient_id>`
- **Local test**: `CLINICAL_NOTES_SOURCE=caboodle python3 -m pytest tests/test_local_agents.py -v`

If you would like to create a personal chat for testing, see [Create Personal Teams Chat](./teams.md#create_personal_chat).

