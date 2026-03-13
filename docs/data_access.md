# Data Access

This document covers the data access layer used to load and format patient data for the GYN Oncology Tumor Board.

## Overview

The Data Access Layer (DAL) abstracts data retrieval from multiple sources — Azure Blob Storage for development/testing and Epic Clarity/Caboodle for production patient data. It provides a unified interface that agent tools use to access clinical notes, pathology reports, radiology reports, and imaging.

### Key Responsibilities

- **Data Retrieval**: Fetch patient data from blob storage, FHIR servers, or Epic Caboodle
- **Data Transformation**: Convert raw data into structured formats for agent processing
- **Data Validation**: Ensure integrity of clinical data being accessed
- **Error Handling**: Manage exceptions during data access operations

### Benefits

- **Abstraction**: Swap data sources (blob → Epic Caboodle) without changing agent tools
- **Reusability**: Centralized data access logic shared across all GYN tumor board tools
- **Maintainability**: Update data source connections without impacting agent logic

### Components

1. **Data Models**: Define the structure of clinical data (notes, reports, images)
2. **Data Accessors**: Implement source-specific retrieval logic

## Data Sources

### Development: Azure Blob Storage
For local development and testing, patient data is stored in Azure Blob Storage under `infra/patient_data/`. Synthetic GYN oncology test cases are provided:
- `patient_gyn_001` — GYN oncology test case
- `patient_gyn_002` — GYN oncology test case

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
| Chat Context | ChatContext | Chat session state including history and loaded patient data |
| Clinical Note | dict | Clinical notes — H&P, consultation, progress notes, referral letters |
| Pathology Report | dict | Surgical pathology, cytology, molecular testing reports |
| Radiology Report | dict | CT, MRI, PET/CT, ultrasound reports |
| Image | binary | Medical images for diagnostic review |

## Data Accessors

| Data Accessor | Description |
|-|-|
| Chat Artifact Accessor | Read/write/archive for ChatArtifact |
| Chat Context Accessor | Read/write/archive for ChatContext |
| Clinical Note Accessor | Read all clinical notes for a patient (used by OncologicHistory agent) |
| Image Accessor | Read medical images |

## Usage of DataAccess in Agents

Agents manage chat history and session data using `ChatContext`. On each message, the agent loads existing `ChatContext` via `DataAccess` or creates a new one. After responding, it saves the updated context.

When an agent receives a "clear" message, the `ChatContext` is archived.

## Usage of DataAccess in Plugins

Plugins receive `PluginConfiguration` at creation. Tools access data models via `PluginConfiguration.data_access`.

```py
class OncologicHistoryExtractorPlugin(MedicalReportExtractorBase):

    async def _get_clinical_notes(self, patient_id: str) -> list[dict]:
        """Read all clinical notes for a patient."""
        accessor = self.data_access.clinical_note_accessor
        all_notes_json = await accessor.read_all(patient_id)
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
