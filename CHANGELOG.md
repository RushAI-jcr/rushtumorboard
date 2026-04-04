# Changelog

All notable changes to the Rush GYN Oncology Tumor Board are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- `.gitattributes` for line ending normalization and binary file handling
- `.editorconfig` for consistent formatting across editors
- `CODEOWNERS` for automatic PR review assignment
- `CHANGELOG.md` (this file)
- GitHub issue templates (bug report, feature request) as YAML forms
- Dependabot monitoring for Python pip, npm, and GitHub Actions dependencies

### Changed
- `CONTRIBUTING.md` rewritten with local dev setup, PHI guidelines, commit conventions, and testing workflow
- `docs/README.md` reorganized with quick-link table and clearer categories
- PR template updated for Python/healthcare project (PHI checklist, agent impact, testing)

### Fixed
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
