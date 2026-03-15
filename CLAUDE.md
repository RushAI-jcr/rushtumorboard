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
│   │       ├── patient_data.py           # Load patient records, build timeline
│   │       ├── oncologic_history_extractor.py  # Prior onc history (OSH transfers)
│   │       ├── pathology_extractor.py    # Histology, IHC, molecular markers
│   │       ├── radiology_extractor.py    # CT/MRI/PET/US findings (LLM-based)
│   │       ├── tumor_markers.py          # CA-125/HE4/hCG trending + GCIG
│   │       ├── clinical_trials.py        # ClinicalTrials.gov search + eligibility
│   │       ├── clinical_trials_nci.py    # NCI API wrapper (calls mcp_servers/)
│   │       ├── graph_rag.py              # GraphRAG medical research
│   │       ├── content_export/content_export.py  # 4-column Word doc
│   │       └── presentation_export.py    # 3-slide PPTX with marker chart
│   ├── data_models/
│   │   ├── epic/caboodle_file_accessor.py  # Epic Caboodle CSV/Parquet reader
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
| Orchestrator | — | Facilitator: manages turn order (steps a–i) |
| PatientHistory | patient_data | Loads Epic data, builds chronological timeline |
| OncologicHistory | oncologic_history_extractor | Prior onc history, OSH transfers |
| Pathology | pathology_extractor | Histology, IHC, molecular classification |
| Radiology | radiology_extractor | CT/MRI/PET/US findings |
| PatientStatus | tumor_markers, patient_data | FIGO staging, molecular profile, treatment history |
| ClinicalGuidelines | — | NCCN-based GYN treatment recommendations |
| ClinicalTrials | clinical_trials, clinical_trials_nci | Trial search + eligibility matching |
| MedicalResearch | graph_rag | Research literature via GraphRAG |
| ReportCreation | content_export, presentation_export | Word doc + PPTX generation |

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
cd src && pip install -r requirements.txt
CLINICAL_NOTES_SOURCE=caboodle python -m tests.test_local_agents
```

## Conventions

- Commit messages: `type: description` (feat, fix, docs, refactor)
- Clinical shorthand in tumor board outputs (s/p, dx, bx, LN, mets, etc.)
- FIGO staging for GYN cancers
- All patient data in `infra/patient_data/` is synthetic (no PHI)
