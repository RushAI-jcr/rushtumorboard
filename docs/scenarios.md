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
| Orchestrator | — | Facilitates discussion, manages turn order |
| PatientHistory | `patient_data` | Loads patient record, builds timeline |
| OncologicHistory | `oncologic_history_extractor`, `patient_data` | Extracts structured prior oncologic history from clinical notes |
| Pathology | `pathology_extractor`, `patient_data` | Extracts histology, IHC, molecular markers |
| Radiology | `radiology_extractor`, `patient_data` | Structures imaging findings (CT, MRI, PET/CT, US) |
| PatientStatus | — | Synthesizes FIGO staging, molecular profile, platinum sensitivity |
| ClinicalGuidelines | — | NCCN-based GYN cancer treatment recommendations |
| ClinicalTrials | `clinical_trials_nci` | Searches NCI for eligible trials |
| MedicalResearch | `graph_rag` | GraphRAG-powered research retrieval |
| ReportCreation | `content_export`, `presentation_export` | Generates Word doc + PPTX |

### Tumor Board Flow
The Orchestrator follows steps a–i:
1. **PatientHistory** loads the patient record
2. **OncologicHistory** extracts prior cancer history (especially for OSH transfers)
3. **Pathology** reviews pathology findings
4. **Radiology** reviews imaging
5. **PatientStatus** synthesizes current status
6. **ClinicalGuidelines** provides NCCN recommendations
7. **ClinicalTrials** searches for eligible trials
8. **MedicalResearch** retrieves relevant research
9. **ReportCreation** generates the landscape Word doc and PPTX

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
