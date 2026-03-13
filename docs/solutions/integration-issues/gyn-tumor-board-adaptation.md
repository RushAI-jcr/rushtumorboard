---
title: "Adapting Healthcare Agent Orchestrator for GYN Oncology Tumor Board"
category: integration-issues
date: 2026-03-12
tags:
  - gyn-oncology
  - tumor-board
  - epic-caboodle
  - mcp-server
  - semantic-kernel
  - clinical-trials
  - agent-orchestration
---

# Adapting Healthcare Agent Orchestrator for GYN Oncology Tumor Board

## Problem

The Azure healthcare-agent-orchestrator was built for a generic molecular tumor board with:
- Blob-storage clinical notes (not Epic)
- CXR deep learning model (irrelevant to GYN cancers)
- Basic ClinicalTrials.gov search (no NCI API, no AACT, no GOG/NRG awareness)
- Generic agent instructions without GYN-specific terminology (FIGO staging, GYN biomarkers, NCCN GYN protocols)

It needed to be transformed into a **gynecologic oncology tumor board** system using Epic Clarity/Caboodle data.

## Root Cause

The orchestrator was designed as a general-purpose cancer tumor board accelerator. Specializing it for GYN oncology required changes across all layers: agent instructions, data access, tools, clinical trial search, and export.

## Solution

### Phase 1: GYN-Specific Agent Configuration

**File: `src/scenarios/default/config/agents.yaml`** — Complete rewrite of all 9 agents:

- **Orchestrator**: GYN tumor board moderator with structured case flow
- **PatientHistory**: Emphasizes menopausal status, parity, GYN surgical history
- **Pathology** (NEW): Extracts IHC panel, molecular classification (POLEmut/MMRd/NSMP/p53abn)
- **Radiology**: Removed CXR model dependency, reads report text for CT/MRI/PET
- **PatientStatus**: 30+ GYN fields including FIGO stage, BRCA, HRD, MMR/MSI, platinum sensitivity
- **ClinicalGuidelines**: Full NCCN GYN protocols (ovarian, endometrial, cervical, vulvar, GTD)
- **ClinicalTrials**: Both SK plugin tools AND MCP tools for NCI/GOG/NRG/AACT search
- **MedicalResearch**: GraphRAG index changed to `gyn-onc-index`
- **ReportCreation**: GYN tumor board Word format with FIGO staging section

Key pattern: agents reference each other by name (e.g., `*Orchestrator*`, `*Pathology*`) and yield control with "back to you: *Orchestrator*".

### Phase 2: Epic Caboodle Data Accessor

**File: `src/data_models/epic/caboodle_file_accessor.py`**

```python
class CaboodleFileAccessor:
    # Same interface as ClinicalNoteAccessor (get_patients, get_metadata_list, read, read_all)
    # Plus GYN-specific methods:
    async def get_pathology_reports(self, patient_id) -> list[dict]
    async def get_radiology_reports(self, patient_id) -> list[dict]
    async def get_tumor_markers(self, patient_id) -> list[dict]
    async def get_cancer_staging(self, patient_id) -> list[dict]
    async def get_medications(self, patient_id) -> list[dict]
    async def get_diagnoses(self, patient_id) -> list[dict]
```

- Reads CSV or Parquet files from `{data_dir}/{patient_id}/` directories
- Supports flexible column naming (CamelCase and snake_case)
- Falls back to legacy JSON format for backward compatibility
- Registered in `data_access.py` via `CLINICAL_NOTES_SOURCE=epic` or `caboodle`

### Phase 3: Clinical Trials MCP Server

**File: `src/mcp_servers/clinical_trials_mcp.py`** — FastMCP server with 4 tools:

1. `search_nci_gyn_trials` — NCI Cancer Trials API with GYN disease/biomarker mapping, `X-API-KEY` header support, `phase.phase` parameter
2. `get_gog_nrg_trials` — ClinicalTrials.gov filtered for GOG/NRG cooperative group trials
3. `get_trial_details_combined` — Merges data from ClinicalTrials.gov + NCI APIs
4. `search_aact_trials` — AACT PostgreSQL with graceful fallback when credentials not configured

**File: `src/mcp_app.py`** — Mounted at `/clinical-trials/` alongside existing `/orchestrator/`

Key decisions:
- MCP server runs alongside existing SK plugin (not replacing it)
- NCI API requires `X-API-KEY` header via `NCI_API_KEY` env var
- AACT requires `AACT_USER` and `AACT_PASSWORD` env vars
- All tools return JSON with `error` field on failure instead of raising exceptions

### Phase 4: GYN-Specific Semantic Kernel Tools

Three new SK plugins following the existing pattern (`create_plugin()` factory + `@kernel_function()` decorators):

**`src/scenarios/default/tools/pathology_extractor.py`**
- `extract_pathology_findings(patient_id)` — LLM extracts structured pathology from reports
- Outputs: histologic type, grade, LVSI, IHC panel, molecular results, endometrial molecular classification

**`src/scenarios/default/tools/radiology_extractor.py`**
- `extract_radiology_findings(patient_id)` — LLM extracts structured radiology from reports
- Outputs: tumor measurements, lymph nodes, peritoneal disease, RECIST response assessment

**`src/scenarios/default/tools/tumor_markers.py`**
- `get_tumor_marker_trend(patient_id, marker)` — Time series with trend analysis
- `get_all_tumor_markers(patient_id)` — Summary of all markers
- Calculates: nadir, doubling time, GCIG response criteria, percent change from baseline/nadir

Pattern for accessing data in new tools:
```python
accessor = self.data_access.clinical_note_accessor
if hasattr(accessor, "get_pathology_reports"):
    reports = await accessor.get_pathology_reports(patient_id)
else:
    # Fallback: filter from read_all()
```

### Phase 5: Removed Irrelevant Components

- `cxr_report_gen`, `med_image_parse`, `med_image_insight` — not referenced in agents.yaml (files kept but inactive)
- `healthcare_agents.yaml` — updated to match GYN configuration

### Phase 6: Test Data & Export

**Two synthetic test cases:**

| Case | Directory | Cancer | Key Features |
|------|-----------|--------|-------------|
| 1 | `patient_gyn_001` | HGSC Ovarian, FIGO IIIC | BRCA1+, post-NACT, olaparib maintenance |
| 2 | `patient_gyn_002` | Endometrioid Endometrial, FIGO IBm-MMRd | Lynch syndrome (MLH1), dMMR, surgical staging |

Each case has 7 CSV files: clinical_notes, pathology_reports, radiology_reports, lab_results, cancer_staging, medications, diagnoses.

**Content export** (`content_export.py`) — added GYN fields: `figo_stage`, `molecular_profile`, `tumor_markers`, `surgical_findings`, `board_discussion`.

### Phase 7: PowerPoint Presentation Export

**File: `src/scenarios/default/tools/presentation_export.py`** — NEW SK plugin

Generates a 3-slide PPTX per patient from all agent outputs:
1. **Slide 1 — Patient Overview**: demographics, FIGO stage, molecular profile (6 bullets)
2. **Slide 2 — Clinical Findings**: pathology/radiology bullets + tumor marker trend chart (matplotlib PNG)
3. **Slide 3 — Treatment & Trials**: NCCN recommendations, board consensus, eligible clinical trials

Key design decisions:
- **Content summarization via LLM**: `SlideContent` dataclass with structured output enforces ≤6 bullets per slide, ≤20 words per bullet — prevents overflow
- **Chart embedding**: `matplotlib → BytesIO → slide.shapes.add_picture()` — proven pattern from `timeline_image.py`
- **Template generated programmatically**: `scripts/generate_pptx_template.py` creates `tumor_board_slides.pptx` with named shapes; any designer can regenerate
- **ReportCreation agent** now has both `content_export` (Word) and `presentation_export` (PPTX) tools

**Claude Code Skills** (Anthropic `github.com/anthropics/skills` pattern):
- `.claude/skills/word-export/SKILL.md` — docxtpl reference for Word generation
- `.claude/skills/pptx-export/SKILL.md` — python-pptx reference for PPTX generation

## Prevention / Best Practices

- **When adding new SK plugin tools**: Follow the `create_plugin(PluginConfiguration)` factory pattern, register in `agents.yaml` under the agent's `tools:` list. The tool name maps to the module path `scenarios.{scenario}.tools.{tool_name}`.
- **When adding new MCP tools**: Create in `src/mcp_servers/`, use `FastMCP`, mount in `mcp_app.py` with a dedicated HTTP handler. Reference tools in agent instructions.
- **Data accessor pattern**: Implement the `ClinicalNoteAccessor` interface (`get_patients`, `get_metadata_list`, `read`, `read_all`) and register in `data_access.py`. Add domain-specific methods with `hasattr()` checks in tools for backward compatibility.
- **NCI API**: Use `phase.phase` (not `phase`) for phase filtering. Add `X-API-KEY` header. Response data is in `data[]` (not `trials[]`).
- **Test data**: Keep CSV files per patient in `infra/patient_data/{patient_id}/` with Caboodle column naming conventions.

## Files Changed

| File | Action |
|------|--------|
| `src/scenarios/default/config/agents.yaml` | Rewritten |
| `src/scenarios/default/config/healthcare_agents.yaml` | Updated |
| `src/data_models/epic/__init__.py` | New |
| `src/data_models/epic/caboodle_file_accessor.py` | New |
| `src/data_models/data_access.py` | Edited |
| `src/mcp_servers/__init__.py` | New |
| `src/mcp_servers/clinical_trials_mcp.py` | New |
| `src/mcp_app.py` | Edited |
| `src/scenarios/default/tools/pathology_extractor.py` | New |
| `src/scenarios/default/tools/radiology_extractor.py` | New |
| `src/scenarios/default/tools/tumor_markers.py` | New |
| `src/scenarios/default/tools/content_export/content_export.py` | Edited |
| `src/requirements.txt` | Edited |
| `src/scenarios/default/tools/presentation_export.py` | New |
| `src/scenarios/default/templates/tumor_board_slides.pptx` | New (generated) |
| `scripts/generate_pptx_template.py` | New |
| `src/data_models/tumor_board_summary.py` | Edited (added SlideContent) |
| `src/scenarios/default/tools/clinical_trials_nci.py` | New |
| `.claude/skills/word-export/SKILL.md` | New |
| `.claude/skills/pptx-export/SKILL.md` | New |
| `infra/patient_data/patient_gyn_001/` | New (7 CSV files) |
| `infra/patient_data/patient_gyn_002/` | New (7 CSV files) |
| `docs/plans/2026-03-12-001-feat-gyn-tumor-board-adaptation-plan.md` | New |
| `docs/plans/2026-03-12-002-feat-clinical-trials-mcp-server-plan.md` | New |
| `docs/brainstorms/2026-03-12-clinical-trials-mcp-server-brainstorm.md` | New |

## Cross-References

- Master plan: `docs/plans/2026-03-12-001-feat-gyn-tumor-board-adaptation-plan.md`
- Clinical trials MCP plan: `docs/plans/2026-03-12-002-feat-clinical-trials-mcp-server-plan.md`
- Brainstorm: `docs/brainstorms/2026-03-12-clinical-trials-mcp-server-brainstorm.md`
- Existing SK plugin pattern: `src/scenarios/default/tools/patient_data.py`
- Existing MCP app: `src/mcp_app.py`
- NCI API docs: https://clinicaltrialsapi.cancer.gov/api/v2
- AACT database: https://aact.ctti-clinicaltrials.org/
