---
topic: Clinical Trials MCP Server for GYN Tumor Board
date: 2026-03-12
status: complete
---

# Clinical Trials MCP Server for GYN Tumor Board

## What We're Building

An MCP (Model Context Protocol) server that adds GYN-specific clinical trial search capabilities **alongside** the existing `clinical_trials.py` Semantic Kernel plugin. The MCP server provides additional data sources (NCI Cancer Trials API, AACT database) that the existing plugin doesn't cover, while keeping the current ClinicalTrials.gov search in place.

## Why This Approach

- The existing `clinical_trials.py` plugin works well for ClinicalTrials.gov search with LLM-based eligibility
- Adding NCI API gives access to NCI-sponsored and GOG/NRG Oncology cooperative group trials with richer oncology metadata (structured biomarker fields, disease subtypes)
- AACT PostgreSQL enables complex queries impossible via REST APIs (cross-table joins on eligibility text, trial site filtering, full-text search)
- MCP keeps the trial search modular and reusable — could be used by Claude Desktop or other MCP clients later

## Key Decisions

1. **Architecture**: Add alongside existing plugin, not replace it
   - The ClinicalTrials agent will have access to both the existing Semantic Kernel tools AND MCP tools
   - MCP server provides: `search_nci_gyn_trials`, `query_aact`, `get_gog_nrg_trials`
   - Existing plugin provides: `search_clinical_trials`, `generate_clinical_trial_search_criteria`, `display_more_information_about_a_trial`

2. **Data Sources**: Three sources
   - ClinicalTrials.gov API v2 (existing plugin — keep as is)
   - NCI Cancer Trials API (new, via MCP)
   - AACT PostgreSQL database (new, via MCP)

3. **Eligibility Matching**: LLM-based (same approach as current)
   - Send patient data + trial criteria to reasoning model
   - MCP server returns raw trial data; eligibility assessment happens in the agent via the reasoning model

4. **GYN-Specific Features**:
   - Pre-built GYN cancer type filters (ovarian, endometrial, cervical, vulvar, GTD)
   - GYN biomarker search terms (BRCA, HRD, MMR/MSI, POLE, HER2, PD-L1, FRα)
   - GOG/NRG Oncology trial identification
   - FIGO stage mapping for eligibility

## MCP Tools to Build

### 1. `search_nci_gyn_trials`
- Calls NCI Cancer Trials API: `https://clinicaltrialsapi.cancer.gov/api/v2/trials`
- Params: disease name, biomarker, trial status, phase
- Returns: structured trial list with NCI-specific metadata (disease coding, biomarker fields, trial sites)
- GYN filtering: map cancer_type param to NCI maintype values

### 2. `query_aact`
- Connects to AACT PostgreSQL: `aact-db.ctti-clinicaltrials.org:5432/aact`
- Accepts structured query params (not raw SQL) for safety
- Params: condition terms, intervention terms, biomarker keywords (searched in eligibility criteria text), status, phase
- Returns: trials with eligibility criteria text, interventions, conditions, sites
- Key advantage: full-text search on eligibility criteria for biomarker mentions

### 3. `get_gog_nrg_trials`
- Searches ClinicalTrials.gov and NCI specifically for GOG/NRG Oncology trials
- Filters by lead sponsor containing "GOG" or "NRG" or collaborative group
- Returns: active GOG/NRG trials relevant to the patient's cancer type

### 4. `get_trial_details`
- Fetches detailed information about a specific trial from any source (NCT ID)
- Combines data from ClinicalTrials.gov and NCI if available
- Returns: comprehensive trial summary

## Integration Points

- Mount MCP server as sub-app in existing `mcp_app.py` OR run as separate process
- Update `agents.yaml` ClinicalTrials agent instructions to mention MCP tools are available
- No changes needed to the existing `clinical_trials.py` plugin

## Open Questions

- None — all key decisions resolved.

## Scope

- MVP: `search_nci_gyn_trials` + `get_gog_nrg_trials` (NCI API only, no AACT yet)
- V2: Add `query_aact` (requires AACT account registration)
