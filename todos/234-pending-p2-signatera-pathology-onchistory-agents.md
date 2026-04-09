---
status: pending
priority: p2
issue_id: "234"
tags: [code-review, agent-parity]
dependencies: []
---

# Add Signatera/ctDNA Awareness to Pathology and OncologicHistory Agents

## Problem Statement

Signatera/ctDNA was added to PatientStatus agent and tumor_markers.py but the Pathology and OncologicHistory agents have no instructions to look for or surface ctDNA results. Signatera results sometimes arrive as pathology reports or are mentioned in oncology consult notes — these agents should know to extract them.

## Findings

**Flagged by:** Agent-Native Reviewer (CRITICAL), Kieran Python Reviewer (#5), Architecture Strategist (#2E)

**Scope expanded in 2nd review round:** The gap is deeper than just prompts — structured data paths are also broken:

1. **pathology_extractor.py `layer3_keywords`** — missing "signatera", "ctdna", "natera", "mrd", "circulating tumor". Natera sends Signatera results as clinical lab/path reports that are classified as pathology in some Epic configs. Layer 3 fallback won't find them.
2. **pathology_extractor.py `_GENOMIC_REPORT_KEYWORDS`** — missing "natera", "signatera". These results arrive as genomic report entries.
3. **CaboodleFileAccessor._TUMOR_MARKER_NAMES** — missing "signatera", "ctdna", "natera", "mrd". `get_tumor_markers()` filters by this set, so structured Signatera data in lab_results.csv is silently dropped.
4. **FabricClinicalNoteAccessor._TUMOR_MARKER_NAMES** — same gap (production Fabric path).
5. **OncologicHistory system prompt** — molecular_profile has no explicit Signatera/ctDNA field or extraction guidance.
6. **Pathology agent YAML** — no mention of Signatera in "WHAT TO INCLUDE" section.

**Files to update:**
- `src/scenarios/default/config/agents.yaml` — Pathology + OncologicHistory agent instructions
- `src/scenarios/default/tools/pathology_extractor.py` — layer3_keywords + _GENOMIC_REPORT_KEYWORDS + system prompt
- `src/scenarios/default/tools/oncologic_history_extractor.py` — system prompt (molecular_profile section)
- `src/data_models/epic/caboodle_file_accessor.py` — _TUMOR_MARKER_NAMES
- `src/data_models/fabric/fabric_clinical_note_accessor.py` — _TUMOR_MARKER_NAMES

## Proposed Solutions

### Option A: Full distribution across all 5 files (Recommended)
- Pathology extractor: Add keywords to layer3_keywords and _GENOMIC_REPORT_KEYWORDS
- Pathology agent YAML: Add Signatera to "WHAT TO INCLUDE"
- OncologicHistory: Add ctDNA/Signatera mention in molecular_profile extraction rules
- CaboodleFileAccessor: Add to _TUMOR_MARKER_NAMES
- FabricClinicalNoteAccessor: Add to _TUMOR_MARKER_NAMES
- Effort: Small | Risk: None

## Acceptance Criteria

- [ ] Pathology extractor layer3_keywords include Signatera terms
- [ ] Pathology extractor _GENOMIC_REPORT_KEYWORDS include "natera", "signatera"
- [ ] Pathology agent YAML mentions Signatera/ctDNA
- [ ] OncologicHistory system prompt mentions ctDNA under molecular_profile
- [ ] CaboodleFileAccessor._TUMOR_MARKER_NAMES includes Signatera terms
- [ ] FabricClinicalNoteAccessor._TUMOR_MARKER_NAMES includes Signatera terms
- [ ] `get_tumor_markers()` returns Signatera data from lab_results.csv when present

## Work Log

- 2026-04-09: Created from Phase 2 code review (Agent-Native Reviewer)
