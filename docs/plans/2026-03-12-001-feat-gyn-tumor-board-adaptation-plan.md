---
title: "feat: Adapt Healthcare Agent Orchestrator for GYN Oncology Tumor Board with Epic Clarity/Caboodle"
type: feat
status: active
date: 2026-03-12
---

# Adapt Healthcare Agent Orchestrator for GYN Oncology Tumor Board

## Overview

Transform the existing general-purpose cancer tumor board orchestrator into a **gynecologic oncology tumor board** system that pulls data from **Epic Clarity and Caboodle** data warehouses and connects clinical trials via an **MCP server**.

## Problem Statement

The current repo is configured for a generic molecular tumor board with blob-storage clinical notes, a CXR deep learning model (irrelevant to GYN), and basic ClinicalTrials.gov search. It needs to be specialized for the GYN oncology workflow with:
- Epic Clarity/Caboodle as the data source (clinical notes, path reports, radiology reports)
- GYN-specific agents (FIGO staging, GYN biomarkers, GYN treatment protocols)
- Clinical trials MCP server for richer trial matching
- Removal of irrelevant components (CXR model)

## What Changes

### Phase 1: GYN-Specific Agent Configuration

**File: `src/scenarios/default/config/agents.yaml`**

Rewrite all agent instructions for GYN oncology context:

#### 1.1 Orchestrator Agent
- Update to moderate a GYN tumor board discussion
- Reference GYN cancer types: ovarian, endometrial, cervical, vulvar, vaginal, GTD
- Facilitate structured case presentation: demographics → pathology → imaging → molecular → staging → treatment plan → trials

#### 1.2 PatientHistory Agent (keep, adapt)
- Same tools (load_patient_data, create_timeline, process_prompt)
- Update instructions to emphasize GYN data: menopausal status, parity, surgical history, prior GYN procedures
- Timeline should prioritize: diagnosis date, staging surgery, debulking status, chemo regimens, recurrence dates

#### 1.3 PatientStatus Agent (keep, adapt heavily)
- Update required data fields for GYN:
  - **Demographics**: Age, BMI, menopausal status, gravida/para, ECOG
  - **Cancer**: Primary site (ovary/endometrium/cervix/vulva), histologic type & subtype, grade
  - **Staging**: FIGO stage (2023 for endometrial, 2018 for cervical, 2014 for ovarian), TNM
  - **Biomarkers**: BRCA1/2 (germline + somatic), HRD score, MMR/MSI, p53, POLE, HER2, PD-L1 CPS, ER/PR, FRα, TMB, NTRK, PIK3CA
  - **Surgical**: Debulking status (R0/optimal/suboptimal), residual disease, lymph node status, LVSI
  - **Treatment**: Lines of therapy, platinum sensitivity interval, prior PARP inhibitor, prior immunotherapy

#### 1.4 Pathology Agent (NEW — replaces Radiology for primary review)
- Reviews pathology reports from Epic
- Extracts: histologic type, grade, margins, LVSI, lymph node counts, IHC panel (p53, ER, PR, WT1, p16, napsin-A), molecular results
- Identifies molecular classification for endometrial (POLEmut, MMRd, p53abn, NSMP)
- Tool: `extract_pathology_findings` (new kernel function)

#### 1.5 Radiology Agent (adapt — remove CXR model, use report text)
- Remove `cxr_report_gen` tool dependency entirely
- Instead, read radiology reports from Epic (CT, MRI, PET/CT, US)
- Summarize findings: tumor measurements, lymphadenopathy, peritoneal disease burden, ascites, distant metastases
- Tool: `extract_radiology_findings` (new kernel function using LLM on report text)
- No deep learning model needed — LLM interprets radiology report narratives

#### 1.6 ClinicalGuidelines Agent (adapt)
- Replace generic oncology guidelines with GYN-specific NCCN protocols:
  - Ovarian: PDS vs NACT decision, platinum-based chemo, PARP inhibitor maintenance (based on BRCA/HRD), bevacizumab
  - Endometrial: Risk stratification by molecular classification (2023 FIGO), adjuvant RT vs chemo vs observation
  - Cervical: Concurrent chemoradiation, pembrolizumab for PD-L1+, tisotumab vedotin
  - Vulvar: Surgical vs chemoradiation based on stage
  - GTD: WHO scoring, single-agent vs multi-agent chemo
- Reference key trials: SOLO1, PAOLA-1, PRIMA, KEYNOTE-826, RUBY, DUO-E, DESTINY

#### 1.7 ClinicalTrials Agent (adapt + MCP)
- Connect via MCP server (see Phase 3)
- GYN-specific search: filter by GOG/NRG Oncology trials, GYN histologies, GYN biomarkers
- Add FIGO stage mapping to eligibility matching

#### 1.8 MedicalResearch Agent (keep, reindex)
- GraphRAG index should be rebuilt for GYN oncology literature (not NSCLC)
- Update `graph_rag_index_name` in agent config to GYN-specific index

#### 1.9 ReportCreation Agent (adapt template)
- Update Word template for GYN tumor board format
- Sections: Demographics, Presenting Complaint, Pathology Review, Imaging Review, Molecular Profile, FIGO Staging, Treatment History, Board Discussion, Consensus Recommendation, Clinical Trials

---

### Phase 2: Epic Caboodle Data Accessor

**Testing:** `src/data_models/epic/caboodle_file_accessor.py` — reads CSV/Parquet exports from Caboodle
**Production:** Adapt existing `FabricClinicalNoteAccessor` to query Caboodle tables in Microsoft Fabric

#### 2.1 Testing Approach (CSV/Parquet Files)

Set `CLINICAL_NOTES_SOURCE=epic` or `CLINICAL_NOTES_SOURCE=caboodle` and `CABOODLE_DATA_DIR` pointing to local exports.

#### 2.2 Data Queries

**Clinical Notes** (from Clarity):
```sql
SELECT hi.NOTE_ID, hi.NOTE_TYPE, hi.ENTRY_TIME, hi.IP_NOTE_TYPE_C,
       hnt.NOTE_TEXT, hnt.LINE
FROM HNO_INFO hi
JOIN HNO_NOTE_TEXT hnt ON hi.NOTE_ID = hnt.NOTE_ID
WHERE hi.PAT_ID = @PatientID
ORDER BY hi.ENTRY_TIME DESC
```

**Pathology Reports** (from Clarity):
```sql
SELECT op.ORDER_PROC_ID, op.PROC_NAME, op.ORDER_TIME,
       orr.ORD_VALUE, orc.COMMENTS
FROM ORDER_PROC op
JOIN ORDER_RESULTS orr ON op.ORDER_PROC_ID = orr.ORDER_PROC_ID
LEFT JOIN ORDER_RES_COMP_CMT orc ON orr.ORDER_PROC_ID = orc.ORDER_PROC_ID
    AND orr.LINE = orc.LINE_COMP
WHERE op.PAT_ID = @PatientID
    AND op.PROC_CAT_C IN (/* pathology category codes */)
ORDER BY op.ORDER_TIME DESC
```

**Radiology Reports** (from Clarity):
```sql
SELECT op.ORDER_PROC_ID, op.PROC_NAME, op.ORDER_TIME,
       orr.ORD_VALUE, orc.COMMENTS
FROM ORDER_PROC op
JOIN ORDER_RESULTS orr ON op.ORDER_PROC_ID = orr.ORDER_PROC_ID
LEFT JOIN ORDER_RES_COMP_CMT orc ON orr.ORDER_PROC_ID = orc.ORDER_PROC_ID
    AND orr.LINE = orc.LINE_COMP
WHERE op.PAT_ID = @PatientID
    AND op.PROC_CAT_C IN (/* radiology category codes */)
ORDER BY op.ORDER_TIME DESC
```

**Lab Results / Tumor Markers** (from Clarity):
```sql
SELECT op.ORDER_TIME, orr.COMPONENT_ID, cc.NAME as COMPONENT_NAME,
       orr.ORD_VALUE, orr.REFERENCE_UNIT, orr.RESULT_FLAG_C
FROM ORDER_PROC op
JOIN ORDER_RESULTS orr ON op.ORDER_PROC_ID = orr.ORDER_PROC_ID
JOIN CLARITY_COMPONENT cc ON orr.COMPONENT_ID = cc.COMPONENT_ID
WHERE op.PAT_ID = @PatientID
    AND orr.COMPONENT_ID IN (/* CA-125, HE4, hCG, AFP, LDH component IDs */)
ORDER BY op.ORDER_TIME DESC
```

**Cancer Staging** (from Clarity/Caboodle):
```sql
SELECT cs.STAGE_DATE, cs.TNM_T, cs.TNM_N, cs.TNM_M,
       cs.STAGE_GROUP, cs.STAGING_SYSTEM
FROM CANCER_STAGING cs
WHERE cs.PAT_ID = @PatientID
ORDER BY cs.STAGE_DATE DESC
```

#### 2.3 Interface Implementation

```python
class EpicClarityAccessor:
    """Same interface as ClinicalNoteAccessor, FhirClinicalNoteAccessor, FabricClinicalNoteAccessor"""

    async def get_patients(self) -> list[str]:
        """Return list of patient IDs"""

    async def get_metadata_list(self, patient_id: str) -> list[dict]:
        """Return metadata for all clinical documents (notes, path, rad)"""

    async def read(self, patient_id: str, note_id: str) -> dict:
        """Read a single clinical document by ID"""

    async def read_all(self, patient_id: str) -> list[dict]:
        """Read all clinical documents for a patient"""

    # GYN-specific additions:
    async def get_pathology_reports(self, patient_id: str) -> list[dict]:
        """Get pathology reports specifically"""

    async def get_radiology_reports(self, patient_id: str) -> list[dict]:
        """Get radiology reports specifically"""

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """Get CA-125, HE4, hCG trends"""

    async def get_cancer_staging(self, patient_id: str) -> list[dict]:
        """Get FIGO/TNM staging records"""
```

#### 2.4 Register in Data Access Factory

**File: `src/data_models/data_access.py`**

Add `CLINICAL_NOTES_SOURCE = "epic"` option:

```python
elif source == "epic":
    from data_models.epic.epic_clarity_accessor import EpicClarityAccessor
    clinical_note_accessor = EpicClarityAccessor(credential)
```

---

### Phase 3: Clinical Trials MCP Server

**New file: `src/mcp_servers/clinical_trials_mcp.py`**

Build a standalone MCP server that wraps multiple clinical trial data sources:

#### 3.1 MCP Tools

```python
from mcp.server.fastmcp import FastMCP

app = FastMCP("clinical-trials-gyn")

@app.tool()
async def search_gyn_trials(
    cancer_type: str,          # "ovarian", "endometrial", "cervical", "vulvar"
    histology: str = None,     # "high-grade serous", "endometrioid", etc.
    biomarkers: list[str] = None,  # ["BRCA1", "HRD", "MSI-H", "PD-L1"]
    stage: str = None,         # FIGO stage
    line_of_therapy: str = None,  # "first-line", "recurrent", "platinum-resistant"
    ecog: int = None,
    age: int = None,
) -> dict:
    """Search ClinicalTrials.gov for recruiting GYN oncology trials"""

@app.tool()
async def search_nci_gyn_trials(
    disease: str,
    biomarker: str = None,
) -> dict:
    """Search NCI Cancer Clinical Trials API for GYN trials"""

@app.tool()
async def get_trial_details(nct_id: str) -> dict:
    """Get full details of a specific trial by NCT ID"""

@app.tool()
async def check_trial_eligibility(
    nct_id: str,
    patient_age: int,
    patient_ecog: int,
    patient_biomarkers: list[str],
    patient_histology: str,
    patient_stage: str,
    prior_therapies: list[str],
) -> dict:
    """Check if a patient meets eligibility criteria for a specific trial"""

@app.tool()
async def search_gog_nrg_trials(
    cancer_type: str,
) -> dict:
    """Search specifically for GOG/NRG Oncology cooperative group trials"""
```

#### 3.2 Integration with Orchestrator

**Option A (Recommended):** Mount as sub-application in existing MCP app:

```python
# In src/mcp_app.py, add the clinical trials MCP as a sub-route
# The ClinicalTrials agent calls these tools via MCP protocol
```

**Option B:** Standalone server that the ClinicalTrials agent connects to as an MCP client.

#### 3.3 Update ClinicalTrials Agent

Modify `clinical_trials.py` to use MCP tools instead of direct API calls. The agent's `search_clinical_trials` function would call the MCP server's `search_gyn_trials` tool, which handles the API orchestration (ClinicalTrials.gov + NCI + GOG/NRG).

---

### Phase 4: New GYN-Specific Tools

#### 4.1 Pathology Extraction Tool

**New file: `src/scenarios/default/tools/pathology_extractor.py`**

```python
class PathologyExtractorPlugin:
    @kernel_function()
    async def extract_pathology_findings(self, patient_id: str) -> str:
        """Extract structured pathology findings from Epic reports using LLM"""
        # 1. Fetch pathology reports from Epic
        # 2. Use LLM to extract structured data:
        #    - Histologic type and grade
        #    - Margins, LVSI, depth of invasion
        #    - Lymph node status
        #    - IHC panel (p53, ER, PR, MMR proteins, HER2)
        #    - Molecular results (BRCA, HRD, MSI, POLE, TMB)
        #    - Endometrial molecular classification (POLEmut/MMRd/p53abn/NSMP)
        # 3. Return structured JSON
```

#### 4.2 Radiology Report Tool (replaces CXR model)

**New file: `src/scenarios/default/tools/radiology_extractor.py`**

```python
class RadiologyExtractorPlugin:
    @kernel_function()
    async def extract_radiology_findings(self, patient_id: str) -> str:
        """Extract structured radiology findings from Epic reports using LLM"""
        # 1. Fetch radiology reports from Epic (CT, MRI, PET/CT, US)
        # 2. Use LLM to extract:
        #    - Primary tumor measurements
        #    - Lymph node status and measurements
        #    - Peritoneal disease burden
        #    - Ascites (present/absent, volume)
        #    - Distant metastases
        #    - RECIST measurements if follow-up scan
        # 3. Return structured JSON
```

#### 4.3 Tumor Marker Trending Tool

**New file: `src/scenarios/default/tools/tumor_markers.py`**

```python
class TumorMarkerPlugin:
    @kernel_function()
    async def get_tumor_marker_trend(self, patient_id: str, marker: str) -> str:
        """Get CA-125, HE4, or hCG trend from Epic labs"""
        # 1. Query Epic for marker results over time
        # 2. Format as time series
        # 3. Calculate: nadir, doubling time, GCIG response criteria (for CA-125)
```

---

### Phase 5: Remove/Replace Irrelevant Components

| Component | Action | Reason |
|-----------|--------|--------|
| `cxr_report_gen.py` | Remove from agents.yaml, keep file | CXR deep learning model not relevant to GYN |
| `med_image_parse.py` | Remove from agents.yaml | MedImageParse segmentation not needed |
| `med_image_insight.py` | Remove from agents.yaml | MedImageInsight not needed |
| HLS model deployments | Skip in Bicep (`hlsModelDeployment`) | No GPU models needed |
| GraphRAG index | Reindex for GYN literature | Current NSCLC index irrelevant |
| Blob storage clinical notes | Keep as fallback | Epic is primary, blob for dev/test |
| Word template | Rewrite for GYN format | Current template is generic |

---

### Phase 6: Sample GYN Test Data

Create sample patient data for development/testing:

**New file: `infra/patient_data/patient_gyn_001/clinical_notes/`**

Create synthetic GYN cases:
- **Case 1**: 62yo woman, newly diagnosed high-grade serous ovarian cancer, stage IIIC, BRCA1+, s/p suboptimal debulking
- **Case 2**: 55yo woman, endometrial cancer, grade 3 endometrioid, stage IB, MMR deficient (MLH1/PMS2 loss), POLE wild-type
- **Case 3**: 42yo woman, cervical squamous cell carcinoma, stage IIB, PD-L1 CPS 15

Each case needs: clinical notes, pathology report, radiology report, lab results (tumor markers), molecular testing results.

---

## File Change Summary

| File | Action |
|------|--------|
| `src/scenarios/default/config/agents.yaml` | **Rewrite** — GYN-specific agent instructions |
| `src/data_models/epic/epic_clarity_accessor.py` | **New** — Epic Clarity/Caboodle data connector |
| `src/data_models/epic/__init__.py` | **New** |
| `src/data_models/data_access.py` | **Edit** — add `epic` source option |
| `src/scenarios/default/tools/pathology_extractor.py` | **New** — pathology report extraction |
| `src/scenarios/default/tools/radiology_extractor.py` | **New** — radiology report extraction (replaces CXR model) |
| `src/scenarios/default/tools/tumor_markers.py` | **New** — tumor marker trending |
| `src/mcp_servers/clinical_trials_mcp.py` | **New** — clinical trials MCP server |
| `src/scenarios/default/tools/clinical_trials.py` | **Edit** — add GYN-specific search, MCP integration |
| `src/scenarios/default/tools/content_export/templates/tumor_board_template.docx` | **Replace** — GYN tumor board format |
| `src/scenarios/default/tools/content_export/content_export.py` | **Edit** — GYN-specific export fields |
| `infra/patient_data/patient_gyn_*/` | **New** — synthetic GYN test cases |
| `src/requirements.txt` | **Edit** — add pyodbc/aioodbc for Epic SQL |

## Implementation Order

1. **Start with agents.yaml** — rewrite agent instructions (immediate impact, no code changes)
2. **Build Epic accessor** — core data pipeline
3. **Build new tools** — pathology extractor, radiology extractor, tumor markers
4. **Build clinical trials MCP** — enhanced trial matching
5. **Create test data** — synthetic GYN cases for development
6. **Update content export** — GYN tumor board Word template
7. **Reindex GraphRAG** — GYN oncology literature

## Acceptance Criteria

- [x] All agents reference GYN-specific terminology, staging (FIGO), and biomarkers
- [x] Epic Clarity accessor can query clinical notes, pathology reports, radiology reports, tumor markers
- [x] CXR model removed from active agent configuration
- [x] Pathology agent extracts structured findings including molecular classification
- [x] Radiology agent summarizes CT/MRI/PET findings from report text (no deep learning)
- [x] Tumor marker trending shows CA-125/HE4/hCG over time
- [x] Clinical trials MCP server searches ClinicalTrials.gov + NCI with GYN-specific filters
- [x] At least 2 synthetic GYN test cases work end-to-end
- [x] Word export produces GYN-formatted tumor board summary
