# CLAUDE.md

## Repository

- **GitHub:** https://github.com/RushAI-jcr/rushtumorboard
- **Upstream fork:** [Azure-Samples/healthcare-agent-orchestrator](https://github.com/Azure-Samples/healthcare-agent-orchestrator)
- **Branch:** `main`

## Project Overview

GYN Oncology Tumor Board — a forked adaptation of Microsoft's `healthcare-agent-orchestrator` for Rush University Medical Center. Multi-agent system using Semantic Kernel + Azure OpenAI for GYN oncology tumor board case preparation.

## Directory Structure

```
├── src/                         # Python application
│   ├── app.py                   # FastAPI + Starlette entrypoint
│   ├── config.py                # Agent config loader, logging, Azure Monitor
│   ├── group_chat.py            # Semantic Kernel group chat orchestration
│   ├── scenarios/default/
│   │   ├── config/
│   │   │   ├── agents.yaml      # 10 agent definitions (tools, instructions, prompts)
│   │   │   └── healthcare_agents.yaml  # Healthcare agent overrides (currently disabled)
│   │   └── tools/               # Semantic Kernel plugins
│   │       ├── patient_data.py                  # Load records, timeline (TIMELINE_NOTE_TYPES filter)
│   │       ├── medical_report_extractor.py       # Base class: 3-layer note fallback
│   │       ├── oncologic_history_extractor.py    # Prior onc history (OSH transfers)
│   │       ├── pathology_extractor.py            # Histology, IHC, molecular markers
│   │       ├── radiology_extractor.py            # CT/MRI/PET/US findings (LLM-based)
│   │       ├── tumor_markers.py                  # CA-125/HE4/hCG trending + GCIG
│   │       ├── pretumor_board_checklist.py       # Pre-meeting procedure pass (Rush order codes)
│   │       ├── nccn_guidelines.py                # NCCN PDF lookup (Docling + PyMuPDF)
│   │       ├── medical_research.py               # PubMed/EuropePMC/S2 + RISEN synthesis
│   │       ├── clinical_trials.py                # ClinicalTrials.gov search + eligibility
│   │       ├── clinical_trials_nci.py            # NCI API wrapper (calls mcp_servers/)
│   │       ├── graph_rag.py                      # GraphRAG (fallback, not primary)
│   │       ├── validation.py                     # Shared input validation helpers
│   │       ├── content_export/content_export.py  # Landscape 4-column Word doc
│   │       └── presentation_export.py            # 3-slide PPTX with CA-125 chart
│   ├── data_models/
│   │   ├── epic/caboodle_file_accessor.py  # Epic Clarity CSV reader (7 CSVs per patient)
│   │   ├── clinical_note_accessor_protocol.py  # Protocol interface for accessor duck-typing
│   │   ├── data_access.py       # Factory: caboodle | fhir | fabric | blob
│   │   └── ...                  # Pydantic models, accessors
│   ├── mcp_servers/
│   │   └── clinical_trials_mcp.py  # NCI + GOG/NRG + AACT trial search
│   ├── bots/                    # Teams bot adapters
│   ├── routes/                  # FastAPI route handlers
│   └── tests/                   # Local agent tests
├── docs/                        # Markdown documentation + LaTeX architecture doc
├── infra/                       # Azure Bicep IaC + synthetic patient data
│   └── patient_data/
│       ├── patient_gyn_001/     # Synthetic GYN case (CSV files)
│       ├── patient_gyn_002/     # Synthetic GYN case (CSV files)
│       └── patient_4/           # Legacy generic case (JSON clinical notes)
├── democlient/                  # React/TypeScript chat UI
├── notebooks/                   # Jupyter test notebooks
├── scripts/                     # Deployment + dev setup scripts
├── teamsApp/                    # Teams app manifest
├── .github/workflows/           # GitHub Actions CI/CD
└── .azdo/pipelines/             # Azure DevOps pipelines
```

## Agents (10 total, defined in agents.yaml)

| Agent | Tools | Role |
|-------|-------|------|
| Orchestrator | — | Facilitator: manages turn order (step 0 + steps a–i) |
| PatientHistory | patient_data | Loads Epic Clarity CSV, builds timeline filtered to 55 NoteTypes |
| OncologicHistory | oncologic_history_extractor, patient_data | Prior onc history, OSH transfers |
| Pathology | pathology_extractor, patient_data | Histology, IHC, molecular classification (POLEmut/MMRd/NSMP/p53abn) |
| Radiology | radiology_extractor, patient_data | CT/MRI/PET/US findings, RECIST tracking |
| PatientStatus | tumor_markers, pretumor_board_checklist | Step 0: pre-meeting procedure pass; FIGO staging, platinum sensitivity |
| ClinicalGuidelines | nccn_guidelines | NCCN-based GYN recommendations from loaded PDF guidelines |
| ClinicalTrials | clinical_trials, clinical_trials_nci | Trial search + eligibility matching (NCI + AACT) |
| MedicalResearch | medical_research | PubMed/EuropePMC/S2 search with RISEN synthesis + citation validation |
| ReportCreation | content_export, presentation_export | Landscape 4-column Word doc + 3-slide PPTX generation |

## Tech Stack

- Python 3.12+, Semantic Kernel (Microsoft), Azure OpenAI (GPT-4o/4.1 + o3-mini)
- FastAPI + Starlette, aiohttp
- docxtpl (Word), python-pptx (PowerPoint), matplotlib (charts)
- Epic Caboodle CSV/Parquet file accessor for clinical data
- MCP protocol for clinical trials server

## Local Development

```sh
cp src/.env.sample src/.env
# Fill in Azure OpenAI credentials, then:
cd src && SCENARIO=default pip3 install -r requirements.txt
CLINICAL_NOTES_SOURCE=caboodle python3 -m pytest tests/test_local_agents.py -v
```

## Conventions

- Commit messages: `type: description` (feat, fix, docs, refactor)
- Clinical shorthand in tumor board outputs (s/p, dx, bx, LN, mets, etc.)
- FIGO staging for GYN cancers
- All patient data in `infra/patient_data/` is synthetic (no PHI)
