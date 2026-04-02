# Scenarios

The orchestrator supports implementing different scenarios side-by-side. The default scenario is a **GYN Oncology Tumor Board**, where 10 specialized agents collaborate to review gynecologic cancer cases in the format used at Rush University Medical Center.

To select a scenario:
```
azd env set SCENARIO <scenario>
```

Then run `azd up` to deploy.

> [!NOTE]
> The current scenario is `default` (GYN Oncology Tumor Board). Follow the instructions below to add additional scenarios.

## Default Scenario: GYN Oncology Tumor Board

The default scenario orchestrates a complete tumor board case review with these agents:

| Agent | Tools | Role |
|-------|-------|------|
| Orchestrator | — | Facilitates discussion, manages turn order; runs pre-meeting checklist as step 0 |
| PatientHistory | `patient_data` | Loads patient record from Epic Clarity CSV, builds chronological timeline |
| OncologicHistory | `oncologic_history_extractor`, `patient_data` | Extracts structured prior oncologic history — diagnosis, treatments, recurrences, referral reason |
| Pathology | `pathology_extractor`, `patient_data` | Extracts histology, IHC panel, molecular markers, FIGO grade, endometrial molecular classification |
| Radiology | `radiology_extractor`, `patient_data` | Structures imaging findings from CT, MRI, PET/CT, US reports using LLM (no deep learning model) |
| PatientStatus | `tumor_markers`, `pretumor_board_checklist` | Step 0: pre-meeting procedure pass; then FIGO staging, molecular profile, platinum sensitivity |
| ClinicalGuidelines | `nccn_guidelines` | NCCN-based GYN treatment recommendations using loaded NCCN PDFs (endometrial, cervical, vaginal, vulvar, ovarian) |
| ClinicalTrials | `clinical_trials`, `clinical_trials_nci` | Searches NCI ClinicalTrials.gov + AACT for eligible trials with GOG/NRG awareness |
| MedicalResearch | `medical_research` | Real-time PubMed/Europe PMC/Semantic Scholar search with RISEN synthesis and citation validation |
| ReportCreation | `content_export`, `presentation_export` | Generates landscape 4-column Word doc + 3-slide PPTX with CA-125 trend chart |

### Tumor Board Flow

The Orchestrator follows a pre-meeting step 0 followed by steps a–i:

- **Step 0** (before step a): **PatientStatus** runs `get_pretumor_board_checklist` to audit required labs, imaging, pathology, and consults. Outstanding items (✗ MISSING or ⚠ STALE) are surfaced to the user for resolution before proceeding.
- **Step a**: **PatientHistory** loads the patient record
- **Step b**: **OncologicHistory** extracts prior cancer history (especially for OSH transfers)
- **Step c**: **Pathology** reviews pathology and molecular findings
- **Step d**: **Radiology** reviews imaging
- **Step e**: **PatientStatus** synthesizes current status (after step 0 checklist is confirmed)
- **Step f**: **ClinicalGuidelines** provides NCCN recommendations
- **Step g**: **ClinicalTrials** searches for eligible trials
- **Step h**: **MedicalResearch** retrieves relevant research
- **Step i**: **ReportCreation** generates the landscape Word doc and PPTX

### Pre-Meeting Procedure Pass

Before any agent presents clinical findings, PatientStatus runs `get_pretumor_board_checklist` as step 0 to verify the case is ready for board review. The checklist audits the following items and returns a ✓ (present and current), ⚠ (present but stale), or ✗ (missing) status for each, along with Epic order codes for any items that need to be placed:

**Labs**
- CBC — required within 14 days (Epic order: LAB002101)
- CMP — required within 14 days (Epic order: LAB002101)
- CA-125 — required within 28 days (Epic order: LAB100623 or similar)

**Imaging**
- CT chest/abdomen/pelvis — required within 56 days (Epic order: RAD100623)
- MRI Pelvis — required within 42 days
- PET/CT — conditional (ordered based on clinical indication, not required for all cancer types)

**Pathology and Molecular**
- Pathology report (surgical or outside hospital)
- IHC panel: MMR (MLH1/MSH2/MSH6/PMS2), p53, ER, HER2
- NGS/molecular panel (e.g., FoundationOne CDx, Tempus xT)
- Germline testing result or order confirmation

**Consults**
- Relevant subspecialty consult notes (e.g., medical oncology, radiation oncology, genetics)

**Cancer-type-conditional items**
- Beta-hCG — required for germ cell tumors and gestational trophoblastic disease (GTD)
- CEA and CA19-9 — required for mucinous histologies
- PET/CT — conditionally required based on cancer type and clinical stage

If any item is ✗ MISSING or ⚠ STALE, the checklist output is surfaced to the user before the board proceeds. The user can resolve outstanding items or confirm they are not applicable before continuing to step a.

### Output Formats

**Word Document**: Landscape 4-column table matching Rush tumor board format:
- Column 1: Diagnosis & Pertinent History
- Column 2: Previous Tx or Operative Findings, Tumor Markers
- Column 3: Imaging
- Column 4: Discussion (with action items in red)

**PowerPoint**: 3-slide summary (Overview, Findings with CA-125 chart, Treatment Plan & Trials)

### Clinical Shorthand
All agents use clinical shorthand style:
- Abbreviations: s/p, dx, bx, LN, mets, OSH, c/w, NACT, IDS, PDS
- Dates: M/D/YY format
- Staging: FIGO staging for GYN cancers
- Markers: CA-125 trends, HE4, HRD score

## Scenario Folder Structure

A scenario is organized under `src/scenarios/<scenario>/`:

- Required:
    - `config/agents.yaml`: Agent definitions with roles and tools
    - `config/healthcare_agents.yaml`: Healthcare-specific agent configs
    - `requirements.txt`: Python dependencies

- Optional:
    - `tools/`: Custom SK plugins for agent tools
    - `templates/`: Document templates (e.g., `tumor_board_template.docx`)
    - `README.md`: Scenario-specific documentation

## Creating a New Scenario

1. Create a new folder under `src/scenarios/`
2. Define at minimum `config/agents.yaml` with at least one `facilitator: true` agent
3. Add `requirements.txt` for dependencies
4. Add the scenario to `infra/main.bicep`:

```bicep
var agentConfigs = {
  default: loadYamlContent('../src/scenarios/default/config/agents.yaml')
  <scenario>: loadYamlContent('../src/scenarios/<scenario>/config/agents.yaml')
}
```

5. Deploy:
```bash
azd env set SCENARIO <scenario>
azd up
```

## Tips for Defining an Orchestrator Agent

### 1. Define Clear Facilitation Responsibilities
- Mark as facilitator: `facilitator: true`
- Limit domain expertise — the orchestrator coordinates, not diagnoses
- Focus on process over content

### 2. Design Effective Turn Management
- Specify handoff protocols: agents return control with "back to you: *Orchestrator*"
- Use direct addressing: "*AgentName*, please..."
- Include agent reference list via `{{aiAgents}}` placeholder

### 3. Include Planning and Transparency
- Have the orchestrator explain the discussion flow upfront
- Request user confirmation before proceeding

### 4. Set Clear Role Boundaries
- Explicitly state what the orchestrator should NOT do
- Define delegation patterns for specialist agents

### 5. Track Progress
- Prevent premature conclusion — check all agents have contributed
- Support follow-up questions after initial review
