# Data Access

This document covers the data access layer used to load and format patient data for the GYN Oncology Tumor Board.

## Overview

The Data Access Layer (DAL) abstracts data retrieval from multiple sources — local Epic Caboodle CSV files for development and Epic Clarity/Caboodle for production patient data. It provides a unified interface that agent tools use to access clinical notes, pathology reports, radiology reports, and imaging.

### Key Responsibilities

- **Data Retrieval**: Fetch patient data from local CSV files, FHIR servers, or Epic Caboodle
- **Data Transformation**: Convert raw data into structured formats for agent processing
- **Data Validation**: Ensure integrity of clinical data being accessed
- **Error Handling**: Manage exceptions during data access operations

### Benefits

- **Abstraction**: Swap data sources (local CSV → Epic Caboodle → FHIR) without changing agent tools
- **Reusability**: Centralized data access logic shared across all GYN tumor board tools
- **Maintainability**: Update data source connections without impacting agent logic

### Components

1. **Data Models**: Define the structure of clinical data (notes, reports, images)
2. **Data Accessors**: Implement source-specific retrieval logic

## Data Sources

### Local Development: Epic Caboodle CSV Files

For local development, patient data is read directly from Epic Caboodle CSV exports stored under `infra/patient_data/`. This is the primary local development pattern:

```sh
CLINICAL_NOTES_SOURCE=caboodle python -m tests.test_local_agents
```

Each patient folder contains CSV files exported from Epic Caboodle:
- `clinical_notes.csv` — all clinical note types (H&P, consults, telephone encounters, etc.)
- `lab_results.csv` — lab results with values, units, reference ranges, and dates
- `radiology_reports.csv` — structured radiology report text
- `pathology_reports.csv` — surgical pathology and cytology report text

Synthetic test cases are provided for development without PHI:
- `patient_gyn_001` — GYN oncology test case
- `patient_gyn_002` — GYN oncology test case

Real patient data folders (15 GUID-named folders from Rush) are present locally but gitignored.

### Production: Epic Clarity/Caboodle

For production deployments at Rush, data is retrieved from Epic's Clarity/Caboodle data warehouse. Configure the data source:

```sh
azd env set CLINICAL_NOTES_SOURCE fhir
```

See the [FHIR Integration Guide](./fhir_integration.md) for Azure Health Data Services or the [Fabric Integration Guide](./fabric/fabric_integration.md) for Microsoft Fabric.

## Data Models

| Data Model | Type | Description |
|-|-|-|
| Chat Artifact | ChatArtifact | Stores generated data from agents: patient timeline, extracted findings, research results |
| Chat Context | ChatContext | Chat session state including history and loaded patient data. `patient_id` is set-once — overwriting with a different ID raises `ValueError` to prevent cross-patient contamination. |
| Clinical Note | dict | Clinical notes — H&P, consultation, progress notes, referral letters |
| Pathology Report | dict | Surgical pathology, cytology, molecular testing reports |
| Radiology Report | dict | CT, MRI, PET/CT, ultrasound reports |
| Image | binary | Medical images for diagnostic review |

## Data Accessors

The clinical note accessor exposes the following methods, all keyed by `patient_id`:

| Method | Returns | Description |
|--------|---------|-------------|
| `read_all(patient_id)` | `list[str\|dict]` | All clinical notes (unfiltered) |
| `get_clinical_notes_by_type(patient_id, note_types)` | `list[dict]` | Notes filtered by NoteType — used by PatientHistory, OncologicHistory |
| `get_clinical_notes_by_keywords(patient_id, keywords)` | `list[dict]` | Notes containing any keyword in text |
| `get_lab_results(patient_id)` | `list[dict]` | Lab results from lab_results.csv |
| `get_radiology_reports(patient_id)` | `list[dict]` | Radiology reports from radiology_reports.csv |
| `get_pathology_reports(patient_id)` | `list[dict]` | Pathology reports from pathology_reports.csv |

Additional accessors:

| Data Accessor | Description |
|-|-|
| Chat Artifact Accessor | Read/write/archive for ChatArtifact |
| Chat Context Accessor | Read/write/archive for ChatContext |
| Image Accessor | Read medical images |

### ClinicalNoteAccessorProtocol

`src/data_models/clinical_note_accessor_protocol.py` defines a Protocol interface (structural subtyping) for the clinical note accessor. This enables duck-typing compatibility across the three accessor implementations — `CaboodleFileAccessor` (local CSV), `FhirClinicalNoteAccessor`, and `FabricClinicalNoteAccessor` — without requiring a shared base class. Any object that implements the methods in the protocol can be used interchangeably by agent tools.

### FHIR Accessor Session Management

`FhirClinicalNoteAccessor` uses a **shared `aiohttp.ClientSession`** across all requests within a conversation. The session is created lazily on first use, guarded by an `asyncio.Lock` to prevent duplicate initialization under concurrent access. Both `fetch_all_entries` and `read()` use this shared session — only `read_all()` opens its own short-lived session for batch note fetching.

Patient resources with missing or malformed `name` fields are skipped with a warning log rather than raising `KeyError` or `IndexError`, allowing the remaining bundle entries to be returned.

## 3-Layer Note Fallback

`MedicalReportExtractorBase` (the shared base class for `PathologyExtractorPlugin` and `RadiologyExtractorPlugin`) uses a three-layer fallback strategy to locate relevant reports. This is necessary because 11 of 15 real patients in the Rush dataset had their surgery performed at outside hospitals (OSH), meaning their pathology and radiology reports are embedded in clinical notes rather than in the dedicated CSV files.

**Layer 1 — Dedicated CSV file**
The extractor first queries the dedicated CSV (`pathology_reports.csv` or `radiology_reports.csv`). For patients treated at Rush, this is sufficient.

**Layer 2 — NoteType filter on clinical_notes.csv**
If the dedicated file is empty or absent, the extractor filters `clinical_notes.csv` by NoteType. For pathology, relevant types include "Operative Report", "Surgical Pathology Final", and "Unmapped External Note". For radiology, relevant types are queried similarly. This catches OSH reports that Epic maps into the clinical notes stream rather than structured report tables.

**Layer 3 — Keyword match on clinical_notes.csv**
If the NoteType filter returns nothing, the extractor falls back to a keyword search across all note text. For pathology, keywords include "biopsy", "carcinoma", and "immunohistochem". This is a broad catch-all for non-standard OSH note formats.

The extractor uses the first layer that returns results, stopping as soon as it finds content.

## Note Type Filtering

PatientHistory uses a curated list of NoteTypes — `TIMELINE_NOTE_TYPES` — containing 55 confirmed NoteType values to filter which notes are sent to GPT when building the patient timeline. This is essential for managing token cost and model context quality.

Without filtering, a typical patient record contains 640–880 clinical notes. The raw note distribution includes approximately 582 Telephone Encounter notes and 203 Care Plan notes per patient. These are high-volume but low-information-density note types that add noise to timeline construction without improving clinical accuracy.

With `TIMELINE_NOTE_TYPES` filtering, approximately 579 of 880 notes are included per patient, removing around 301 noise notes. The filtered set retains H&P notes, consultation notes, operative reports, discharge summaries, progress notes, and other clinically relevant types, while excluding telephone encounters, care plans, and other administrative note types.

OncologicHistory uses the same `get_clinical_notes_by_type` method with its own targeted NoteType list focused on notes most likely to contain prior oncologic history, OSH transfer records, and referral documentation.

## Usage of DataAccess in Agents

Agents manage chat history and session data using `ChatContext`. On each message, the agent loads existing `ChatContext` via `DataAccess` or creates a new one. After responding, it saves the updated context.

When an agent receives a "clear" message, the `ChatContext` is archived.

## Usage of DataAccess in Plugins

Plugins receive `PluginConfiguration` at creation. Tools access data models via `PluginConfiguration.data_access`.

```py
class OncologicHistoryExtractorPlugin(MedicalReportExtractorBase):

    async def _get_clinical_notes(self, patient_id: str) -> list[dict]:
        """Read clinical notes filtered by NoteType for oncologic history."""
        accessor = self.data_access.clinical_note_accessor
        notes = await accessor.get_clinical_notes_by_type(patient_id, ONCOLOGIC_NOTE_TYPES)
        # Parse and return notes...
```

Generic pattern for any plugin:

```py
class SamplePlugin:

    def __init__(self, config: PluginConfiguration):
        self.config = config

    @kernel_function()
    async def tool1(self, patient_id: str) -> str:
        clinical_notes = await self.config.data_access.clinical_note_accessor.read_all(patient_id)
        # Process clinical notes...
```
