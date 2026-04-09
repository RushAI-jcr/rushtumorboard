# Changelog

All notable changes to the Rush GYN Oncology Tumor Board are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Genomic variant pipeline** — `variant_details.csv` and `variant_interpretation.csv` support in CaboodleFileAccessor and FabricClinicalNoteAccessor; filters to 40+ actionable GYN oncology genes (BRCA1/2, HRD, POLE, TP53, MMR, PIK3CA, NTRK, HER2, etc.); pathology extractor merges genomic variants with structured pathology findings
- **Signatera/ctDNA tumor marker support** — added to `tumor_markers.py`, `pretumor_board_checklist.py`, Caboodle and Fabric accessors, pathology/oncologic history extractors, and content/presentation export prompts
- **Expanded imaging modality coverage** — 25+ new keywords for CT RP, CT AP, TVUS, pelvic US, FDG-PET, bone scan, DEXA, lymphangiogram, nuclear medicine; pending/scheduled imaging flagged with `[PENDING]` tag
- **OSH (outside hospital) flagging** — centralized `imaging_constants.py` with `OSH_HOSPITAL_NAMES` and `RUSH_AFFILIATES` frozensets; referenced across radiology extractor, agents.yaml, content/presentation export, oncologic history extractor; Copley recognized as Rush affiliate
- **MRN→GUID resolution** — lazy-built index from `patient_demographics.csv` files; asyncio.Lock with double-check pattern; path traversal protection via `Path.resolve().is_relative_to()`
- **Handout audit script** (`scripts/audit_handout_vs_data.py`) — compares tumor board handout (.docx) against CSV data, produces per-patient gap report
- **Content export shared module** (`content_export/_shared.py`) — extracted shared data preparation logic used by both Word and PPTX exports
- `.gitattributes` for line ending normalization and binary file handling
- `.editorconfig` for consistent formatting across editors
- `CODEOWNERS` for automatic PR review assignment
- `CHANGELOG.md` (this file)
- GitHub issue templates (bug report, feature request) as YAML forms
- Dependabot monitoring for Python pip, npm, and GitHub Actions dependencies

### Changed
- CaboodleFileAccessor now handles 10 CSVs per patient (added `patient_demographics`, `variant_details`, `variant_interpretation`)
- Column alias normalization in CaboodleFileAccessor (handles March vs April export differences)
- Per-file-type date lookback windows: clinical notes 90d, labs 1yr, pathology/radiology/staging all data
- LRU cache with per-patient eviction (max 5 patients in heap, HIPAA: limit PHI in memory)
- Radiology extractor `layer3_keywords` pruned from 81 to 52 entries (removed redundant substring-subsumed keywords, hospital names moved to LLM prompt, "scheduled"/"ordered"/"pending" removed to prevent over-matching)
- Pre-tumor board checklist expanded: conditional checks for TVUS, bone scan, lymphangiogram, CT RP, Signatera/ctDNA
- `CONTRIBUTING.md` rewritten with local dev setup, PHI guidelines, commit conventions, and testing workflow
- `docs/README.md` reorganized with quick-link table and clearer categories
- PR template updated for Python/healthcare project (PHI checklist, agent impact, testing)

### Fixed
- **HIPAA: MRN plaintext logging** — MRN values masked to last 4 digits in all log output; parse script masks MRN/name/DOB in console
- **Path traversal** in `resolve_patient_id` and `_read_file` — added `is_relative_to` guards preventing cross-patient data reads
- **Race condition** on lazy MRN index build — added asyncio.Lock with double-check pattern
- **Bare except** in `_build_mrn_index_sync` narrowed to `(OSError, csv.Error, UnicodeDecodeError)`
- **CT RP clinical correctness** — moved to own pattern list so CT retroperitoneum doesn't satisfy CT CAP checklist
- **Keyword matching performance** — hoisted `.lower()` out of inner `any()` loop in `get_clinical_notes_by_keywords` and `clinical_note_filter_utils`
- 13 code review findings in `group_chat.py` (4 P1, 6 P2, 3 P3):
  - Removed PHI-leaking diagnostic `invoke()` override
  - Capped `self.messages` and canonical history to prevent unbounded memory growth
  - Changed termination default from terminate to continue on parse failure (clinical safety)
  - Narrowed bare `Exception` catches to `(ValidationError, ValueError)`
  - Extracted `_is_tool_message()` helper (DRY)
  - Added SK private API assertion guard for version compatibility
  - Added agent dependency ordering to selection prompt
  - Added anti-injection preamble to selection and termination prompts
  - Moved all imports to module scope
  - Added SCENARIO/tool_name regex validation before dynamic import

### Security
- 6 P1 security findings resolved: FHIR session leak, MCP endpoint auth, MCP PHI logging, stub mixin silent failures, MCP facilitator mode, MCP missing request date
- WebSocket connection auth hardened: reject unauthenticated before accept
- File type allowlist (`_VALID_FILE_TYPES`) prevents adversarial `file_type` values
- Data factory fallthrough now raises ValueError for invalid `CLINICAL_NOTES_SOURCE`

## [0.3.0] - 2026-03-28

### Added
- Cervical cancer NCCN guidelines (CERV-1 through CERV-G)
- GTN test patient (`patient_gyn_003`)
- NCCN cancer type mapping refactor for multi-cancer support
- Ovarian, cervical, and GTN NCCN guideline PDFs
- Agent token limits per agent configuration

### Fixed
- Pyright type errors across MCP and tool files
- Pre-commit hook PHI blocklist restored after history scrub
- Real patient GUIDs removed from all tracked files (HIPAA remediation)

## [0.2.0] - 2026-03-18

### Added
- Clinical trials MCP server (6 FastMCP tools: NCI + GOG/NRG + AACT)
- Clinical trials eligibility matcher with NCI API
- Batch end-to-end test runner (`scripts/run_batch_e2e.py`) for 15 patients
- MCP integration with Copilot Studio
- Medical research agent with PubMed/Europe PMC/Semantic Scholar + RISEN synthesis
- Pre-meeting procedure checklist with Rush Epic order codes
- Tumor marker trending (CA-125, HE4, hCG) with GCIG criteria
- Content export: landscape 5-column Word doc + 5-slide PPTX with CA-125 chart

### Changed
- Data access layer: 3-layer note fallback (dedicated CSV, NoteType filter, keyword filter)
- Pathology extractor: endometrial molecular classification (POLEmut/MMRd/NSMP/p53abn)
- Radiology extractor: RECIST tracking, PCI scoring

## [0.1.0] - 2026-03-12

### Added
- Initial GYN oncology adaptation of Microsoft healthcare-agent-orchestrator
- 10 specialized agents (Orchestrator, PatientHistory, OncologicHistory, Pathology, Radiology, PatientStatus, ClinicalGuidelines, ClinicalTrials, MedicalResearch, ReportCreation)
- Epic Caboodle CSV file accessor for 7 clinical data types
- NCCN guidelines integration (Docling + PyMuPDF + GPT-4o vision)
- Synthetic test patients (`patient_gyn_001`, `patient_gyn_002`)
- PHI pre-commit hook blocking real patient GUIDs
- GitHub Actions PHI scan workflow

### Changed
- Forked from [Azure-Samples/healthcare-agent-orchestrator](https://github.com/Azure-Samples/healthcare-agent-orchestrator)
- Agents.yaml customized for GYN oncology tumor board workflow
- Orchestrator step order adapted for tumor board clinical flow (step 0 + steps a-i)

[Unreleased]: https://github.com/RushAI-jcr/rushtumorboard/compare/main...HEAD
