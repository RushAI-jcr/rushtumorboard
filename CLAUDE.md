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
│   ├── app.py                   # FastAPI + Starlette entrypoint (+ MCP mount at /mcp)
│   ├── config.py                # Agent config loader, logging, Azure Monitor
│   ├── group_chat.py            # Semantic Kernel group chat orchestration
│   ├── mcp_app.py               # FastMCP app factory for Copilot Studio integration
│   ├── scenarios/default/
│   │   ├── config/
│   │   │   ├── agents.yaml      # 10 agent definitions (tools, instructions, prompts)
│   │   │   ├── shared_agent_footer.md  # Shared security/date/yield rules (appended via addition_instructions)
│   │   │   └── healthcare_agents.yaml  # Healthcare agent overrides (currently disabled)
│   │   └── tools/               # Semantic Kernel plugins
│   │       ├── patient_data.py                  # Load records, timeline (TIMELINE_NOTE_TYPES filter)
│   │       ├── medical_report_extractor.py       # Base class: 3-layer note fallback
│   │       ├── oncologic_history_extractor.py    # Prior onc history (OSH transfers)
│   │       ├── pathology_extractor.py            # Histology, IHC, molecular markers + genomic variants
│   │       ├── radiology_extractor.py            # CT/MRI/PET/US findings (LLM-based, OSH flagging)
│   │       ├── tumor_markers.py                  # CA-125/HE4/hCG/SCC-Ag/Signatera trending + GCIG
│   │       ├── pretumor_board_checklist.py       # Pre-meeting procedure pass (Rush order codes)
│   │       ├── nccn_guidelines.py                # NCCN PDF lookup (Docling + PyMuPDF)
│   │       ├── medical_research.py               # PubMed/EuropePMC/S2 + RISEN synthesis
│   │       ├── clinical_trials.py                # ClinicalTrials.gov search + eligibility
│   │       ├── clinical_trials_nci.py            # NCI API wrapper (calls mcp_servers/)
│   │       ├── graph_rag.py                      # GraphRAG (fallback, not primary)
│   │       ├── validation.py                     # Shared input validation helpers
│   │       ├── note_type_constants.py            # TIMELINE_NOTE_TYPES + extractor NoteType lists
│   │       ├── imaging_constants.py              # OSH hospital names + Rush affiliates (single source of truth)
│   │       ├── content_export/content_export.py  # Landscape 5-column Word doc (docxtpl)
│   │       ├── content_export/_shared.py         # Shared export data preparation (demographics, staging)
│   │       ├── content_export/timeline_image.py  # Timeline image generation helper
│   │       └── presentation_export.py            # 5-slide PPTX via PptxGenJS (Node.js)
│   ├── data_models/
│   │   ├── epic/caboodle_file_accessor.py  # Epic Clarity CSV reader (10 CSVs per patient, MRN→GUID index)
│   │   ├── clinical_note_accessor.py       # Blob-based clinical note accessor
│   │   ├── clinical_note_accessor_protocol.py  # Protocol interface for accessor duck-typing
│   │   ├── accessor_stub_mixin.py          # Mixin for stub accessors (missing CSV graceful handling)
│   │   ├── data_access.py                  # Factory: caboodle | fhir | fabric | blob
│   │   ├── tumor_board_summary.py          # Pydantic models: TumorBoardDocContent, SlideContent
│   │   ├── image_accessor.py               # Medical image accessor
│   │   ├── chat_artifact_accessor.py       # Artifact read/write/archive
│   │   ├── chat_context_accessor.py        # Chat session state accessor
│   │   ├── chat_context.py                 # ChatContext with set-once patient_id
│   │   ├── fhir/fhir_clinical_note_accessor.py  # FHIR server accessor (shared aiohttp session)
│   │   └── fabric/fabric_clinical_note_accessor.py  # Microsoft Fabric accessor
│   ├── mcp_servers/
│   │   └── clinical_trials_mcp.py  # NCI + GOG/NRG + AACT trial search (6 FastMCP tools)
│   ├── bots/                    # Teams bot adapters + access control middleware
│   ├── routes/                  # FastAPI route handlers
│   │   ├── api/                 # chats, messages, user, time
│   │   ├── patient_data/        # Patient CSV upload/access
│   │   └── views/               # Demo routes (disabled by default): timeline, grounded notes
│   ├── utils/                   # date_utils, model_utils, clinical_note_filter_utils, logging_http_client, phi_scrubber, message_enrichment
│   └── tests/                   # Local agent tests + schema alignment tests
├── docs/                        # Markdown documentation
├── infra/                       # Azure Bicep IaC + patient data
│   └── patient_data/
│       ├── patient_gyn_001/     # Synthetic GYN case (CSV files)
│       ├── patient_gyn_002/     # Synthetic GYN case (CSV files)
│       ├── patient_4/           # Legacy generic case (JSON clinical notes)
│       └── <15 UUID folders>/   # Real Rush patient data (gitignored)
├── democlient/                  # React/TypeScript chat UI
├── scripts/                     # Deployment + dev utilities
│   ├── parse_tumor_board_excel.py    # Parse tumor board Excel input to patient CSVs
│   ├── nccn_pdf_processor.py         # NCCN PDF → structured guideline data
│   ├── validate_patient_csvs.py      # Validate patient CSV file integrity
│   ├── audit_handout_vs_data.py      # Compare handout (.docx) vs CSV data — gap report
│   ├── run_batch_e2e.py              # Batch end-to-end test runner (15 patients)
│   ├── generate_docx_template.py     # Generate Word template for content_export
│   ├── generate_pptx_template.py     # Generate PPTX template
│   ├── generate_fhir_resources.py    # Generate FHIR test data
│   └── ingest_fhir_resources.py      # Ingest FHIR data into AHDS
├── teamsApp/                    # Teams app manifest
├── .github/workflows/           # GitHub Actions CI/CD
└── .azdo/pipelines/             # Azure DevOps pipelines
```

## Agents (10 total, defined in agents.yaml)

| Agent | Tools | Deployment | Role |
|-------|-------|------------|------|
| Orchestrator | — | gpt-4.1-mini | Facilitator: manages turn order (step 0 + steps a–i) |
| PatientHistory | patient_data | gpt-4.1 (default) | Loads Epic Clarity CSV, builds timeline filtered to 55 NoteTypes |
| OncologicHistory | oncologic_history_extractor, patient_data | gpt-4.1 (default) | Prior onc history, OSH transfers |
| Pathology | pathology_extractor, patient_data | gpt-4.1 (default) | Histology, IHC, molecular classification (POLEmut/MMRd/NSMP/p53abn) |
| Radiology | radiology_extractor, patient_data | gpt-4.1 (default) | CT/MRI/PET/US findings, RECIST tracking |
| PatientStatus | tumor_markers, pretumor_board_checklist, patient_data | gpt-4.1 (default) | Step 0: pre-meeting procedure pass; FIGO staging, platinum sensitivity |
| ClinicalGuidelines | nccn_guidelines | o4-mini (reasoning) | NCCN-based GYN recommendations from loaded PDFs (all 6 cancer types + Evidence Blocks) |
| ClinicalTrials | clinical_trials, clinical_trials_nci | gpt-5.4 (reasoning, tool-level) | Trial search + eligibility matching (NCI + AACT) |
| MedicalResearch | medical_research | gpt-4.1 (default) | PubMed/EuropePMC/S2 search with RISEN synthesis + citation validation |
| ReportCreation | content_export, presentation_export | gpt-4.1 (default) | Landscape 5-column Word doc + 5-slide PPTX generation |

Selection/termination strategy uses `gpt-4.1-mini` (`AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME`).

## Tech Stack

- Python 3.12+, Semantic Kernel (Microsoft), Azure OpenAI (GPT-4.1 + o4-mini + gpt-5.4)
- FastAPI + Starlette, aiohttp
- docxtpl (Word), PptxGenJS via Node.js (PowerPoint), matplotlib (charts)
- Epic Caboodle CSV/Parquet file accessor for clinical data
- FastMCP protocol for clinical trials server + Copilot Studio integration

## Local Development

```sh
cp src/.env.sample src/.env
# Fill in Azure OpenAI credentials, then:
cd src && pip3 install -r requirements.txt

# Run tests
CLINICAL_NOTES_SOURCE=caboodle python3 -m pytest tests/test_local_agents.py -v

# Run full app (backend + frontend)
cd src && LOCAL_DEV=true python3 -m uvicorn app:app --port 8000 --reload
cd democlient && npm run dev   # frontend at http://localhost:3000
```

`LOCAL_DEV=true` skips Azure Blob Storage and Teams bot adapters. Generated Word/PPTX artifacts are saved to `~/Desktop/dev testing/{patient_id}/`.

## Key Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Primary model for all agents | gpt-4.1 |
| `AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME` | Faster model for agent routing | falls back to primary |
| `AZURE_OPENAI_DEPLOYMENT_NAME_GUIDELINES` | Reasoning model for ClinicalGuidelines | falls back to primary |
| `AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL` | Reasoning model for ClinicalTrials tool | required |
| `EXCLUDED_AGENTS` | Comma-separated agent names to exclude | (empty) |
| `TUMOR_BOARD_DATE` | ISO date (YYYY-MM-DD) for lookback windows | today |
| `CABOODLE_DATA_DIR` | Path to Epic Caboodle CSV patient data | `infra/patient_data` |

## Conventions

- Commit messages: `type: description` (feat, fix, docs, refactor)
- Clinical shorthand in tumor board outputs (s/p, dx, bx, LN, mets, etc.)
- FIGO staging for GYN cancers
- All patient data in `infra/patient_data/` is synthetic (no PHI)
- `agents.yaml` supports `${ENV_VAR}` interpolation for deployment names
