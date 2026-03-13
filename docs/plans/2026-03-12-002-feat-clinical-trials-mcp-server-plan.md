---
title: "feat: Add Clinical Trials MCP Server for GYN Tumor Board"
type: feat
status: active
date: 2026-03-12
origin: docs/brainstorms/2026-03-12-clinical-trials-mcp-server-brainstorm.md
---

# Add Clinical Trials MCP Server for GYN Tumor Board

## Overview

Build an MCP server that adds NCI Cancer Trials API and AACT database search alongside the existing ClinicalTrials.gov Semantic Kernel plugin. The MCP server provides GYN-specific trial matching capabilities including GOG/NRG Oncology cooperative group trial identification.

## Problem Statement / Motivation

The existing `clinical_trials.py` plugin only searches ClinicalTrials.gov via the v2 API. For GYN tumor board, we need:
- NCI-sponsored trials with structured oncology metadata (disease subtypes, biomarker fields)
- GOG/NRG Oncology cooperative group trial identification
- Complex eligibility criteria text search (AACT database)
- GYN-specific biomarker filtering (BRCA, HRD, MMR/MSI, POLE, HER2, PD-L1, FRα)

(see brainstorm: docs/brainstorms/2026-03-12-clinical-trials-mcp-server-brainstorm.md)

## Proposed Solution

Add a new MCP server mounted alongside the existing orchestrator MCP app. The ClinicalTrials agent keeps its existing Semantic Kernel tools AND gains access to new MCP tools for NCI and AACT searches.

## Technical Approach

### Architecture

```
ClinicalTrials Agent
├── Existing SK Plugin (clinical_trials.py)
│   ├── generate_clinical_trial_search_criteria  (ClinicalTrials.gov)
│   ├── search_clinical_trials                    (ClinicalTrials.gov)
│   └── display_more_information_about_a_trial    (ClinicalTrials.gov)
│
└── NEW MCP Server (clinical_trials_mcp.py)
    ├── search_nci_gyn_trials      (NCI Cancer Trials API)
    ├── get_gog_nrg_trials         (ClinicalTrials.gov + NCI, filtered)
    ├── search_aact_trials         (AACT PostgreSQL)
    └── get_trial_details_combined (NCT ID → merged ClinicalTrials.gov + NCI data)
```

### Implementation

#### 1. Create MCP Server

**New file: `src/mcp_servers/clinical_trials_mcp.py`**

```python
from mcp.server.fastmcp import FastMCP
import aiohttp

mcp = FastMCP("clinical-trials-gyn")

@mcp.tool()
async def search_nci_gyn_trials(
    cancer_type: str,          # "ovarian", "endometrial", "cervical", "vulvar"
    biomarkers: str = None,    # comma-separated: "BRCA1,HRD,MSI-H"
    phase: str = None,         # "I", "II", "III", "I/II"
    status: str = "active",    # "active", "approved", "closed"
) -> str:
    """Search NCI Cancer Clinical Trials API for GYN oncology trials.
    Returns trials from the National Cancer Institute including GOG/NRG cooperative group trials."""

    # Map cancer_type to NCI disease terms
    disease_map = {
        "ovarian": "Ovarian Cancer",
        "endometrial": "Endometrial Cancer",
        "cervical": "Cervical Cancer",
        "uterine": "Uterine Cancer",
        "vulvar": "Vulvar Cancer",
        "fallopian": "Fallopian Tube Cancer",
        "peritoneal": "Primary Peritoneal Cancer",
        "gtd": "Gestational Trophoblastic Disease",
    }

    params = {
        "diseases.name": disease_map.get(cancer_type.lower(), cancer_type),
        "current_trial_status": status,
        "size": 20,
    }
    if biomarkers:
        params["biomarkers.name"] = biomarkers.split(",")[0].strip()
    if phase:
        params["phase"] = phase

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://clinicaltrialsapi.cancer.gov/api/v2/trials",
            params=params
        ) as resp:
            data = await resp.json()

    # Format results
    trials = []
    for trial in data.get("data", data.get("trials", [])):
        trials.append({
            "nct_id": trial.get("nct_id"),
            "title": trial.get("brief_title"),
            "phase": trial.get("phase", {}).get("phase") if isinstance(trial.get("phase"), dict) else trial.get("phase"),
            "lead_org": trial.get("lead_org"),
            "principal_investigator": trial.get("principal_investigator"),
            "diseases": [d.get("name") for d in trial.get("diseases", [])],
            "biomarkers": [b.get("name") for b in trial.get("biomarkers", [])],
            "url": f"https://clinicaltrials.gov/study/{trial.get('nct_id')}",
        })

    return json.dumps({"total": data.get("total", len(trials)), "trials": trials}, indent=2)


@mcp.tool()
async def get_gog_nrg_trials(
    cancer_type: str,  # "ovarian", "endometrial", "cervical"
) -> str:
    """Search specifically for GOG/NRG Oncology cooperative group trials for GYN cancers."""

    condition_map = {
        "ovarian": "ovarian cancer",
        "endometrial": "endometrial cancer",
        "cervical": "cervical cancer",
        "uterine": "uterine cancer",
        "vulvar": "vulvar cancer",
    }
    condition = condition_map.get(cancer_type.lower(), cancer_type)

    # Search ClinicalTrials.gov for GOG/NRG sponsored trials
    params = {
        "query.term": f'("{condition}") AND (GOG OR NRG OR "NRG Oncology" OR "Gynecologic Oncology Group")',
        "filter.overallStatus": "RECRUITING",
        "pageSize": 20,
        "fields": "IdentificationModule|ConditionsModule|DesignModule|SponsorCollaboratorsModule",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params=params
        ) as resp:
            data = await resp.json()

    trials = []
    for study in data.get("studies", []):
        protocol = study.get("protocolSection", {})
        id_mod = protocol.get("identificationModule", {})
        design = protocol.get("designModule", {})
        sponsors = protocol.get("sponsorCollaboratorsModule", {})

        trials.append({
            "nct_id": id_mod.get("nctId"),
            "title": id_mod.get("briefTitle"),
            "phase": design.get("phases", []),
            "lead_sponsor": sponsors.get("leadSponsor", {}).get("name"),
            "collaborators": [c.get("name") for c in sponsors.get("collaborators", [])],
            "url": f"https://clinicaltrials.gov/study/{id_mod.get('nctId')}",
        })

    return json.dumps({"total": len(trials), "trials": trials}, indent=2)


@mcp.tool()
async def search_aact_trials(
    condition: str,
    eligibility_keywords: str = None,
    intervention: str = None,
    status: str = "Recruiting",
    limit: int = 20,
) -> str:
    """Search the AACT database (ClinicalTrials.gov mirror) for trials with complex eligibility criteria filtering.
    Useful for finding trials that mention specific biomarkers or treatments in their eligibility text."""

    # Note: AACT requires registration. Connection details from env vars.
    import asyncpg

    conn = await asyncpg.connect(
        host=os.getenv("AACT_HOST", "aact-db.ctti-clinicaltrials.org"),
        port=int(os.getenv("AACT_PORT", "5432")),
        database="aact",
        user=os.getenv("AACT_USER"),
        password=os.getenv("AACT_PASSWORD"),
    )

    query = """
        SELECT s.nct_id, s.brief_title, s.overall_status, s.phase,
               s.start_date, s.enrollment, e.criteria
        FROM ctgov.studies s
        JOIN ctgov.eligibilities e ON s.nct_id = e.nct_id
        JOIN ctgov.conditions c ON s.nct_id = c.nct_id
        WHERE s.overall_status = $1
          AND c.name ILIKE $2
    """
    params = [status, f"%{condition}%"]
    param_idx = 3

    if eligibility_keywords:
        query += f" AND e.criteria ILIKE ${param_idx}"
        params.append(f"%{eligibility_keywords}%")
        param_idx += 1

    if intervention:
        query += f"""
            AND EXISTS (
                SELECT 1 FROM ctgov.interventions i
                WHERE i.nct_id = s.nct_id AND i.name ILIKE ${param_idx}
            )
        """
        params.append(f"%{intervention}%")
        param_idx += 1

    query += f" ORDER BY s.start_date DESC LIMIT ${param_idx}"
    params.append(limit)

    rows = await conn.fetch(query, *params)
    await conn.close()

    trials = [dict(r) for r in rows]
    # Convert date objects to strings
    for t in trials:
        for k, v in t.items():
            if hasattr(v, 'isoformat'):
                t[k] = v.isoformat()

    return json.dumps({"total": len(trials), "trials": trials}, indent=2)


@mcp.tool()
async def get_trial_details_combined(nct_id: str) -> str:
    """Get comprehensive trial details by NCT ID, combining data from ClinicalTrials.gov and NCI APIs."""

    results = {}

    # Fetch from ClinicalTrials.gov
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://clinicaltrials.gov/api/v2/studies/{nct_id}") as resp:
            if resp.status == 200:
                results["clinicaltrials_gov"] = await resp.json()

    # Fetch from NCI
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://clinicaltrialsapi.cancer.gov/api/v2/trials/{nct_id}"
        ) as resp:
            if resp.status == 200:
                results["nci"] = await resp.json()

    return json.dumps(results, indent=2, default=str)
```

#### 2. Mount in MCP App

**Edit: `src/mcp_app.py`**

Add a second MCP mount point for the clinical trials server:

```python
# In create_fast_mcp_app, add route:
Mount("/clinical-trials/", app=clinical_trials_mcp_handler),
```

#### 3. Update Agent Instructions

**Edit: `src/scenarios/default/config/agents.yaml`**

Add a note to the ClinicalTrials agent instructions:

```yaml
# Add to ClinicalTrials agent instructions:
In addition to the standard ClinicalTrials.gov search tools, you also have access to MCP tools:
- search_nci_gyn_trials: Search NCI-sponsored trials with structured GYN oncology metadata
- get_gog_nrg_trials: Find GOG/NRG Oncology cooperative group trials
- search_aact_trials: Search AACT database for complex eligibility criteria matching
- get_trial_details_combined: Get comprehensive details combining ClinicalTrials.gov + NCI data

Use these MCP tools to supplement your ClinicalTrials.gov search, especially for:
- Finding GOG/NRG cooperative group trials
- Searching by specific biomarker eligibility criteria text
- Getting NCI-specific trial metadata
```

#### 4. Add Dependencies

**Edit: `src/requirements.txt`**

```
asyncpg>=0.29.0  # For AACT PostgreSQL queries
```

## Acceptance Criteria

- [ ] MCP server starts and exposes 4 tools at `/mcp/clinical-trials/`
- [ ] `search_nci_gyn_trials` returns trials from NCI API filtered by GYN cancer type
- [ ] `get_gog_nrg_trials` returns GOG/NRG cooperative group trials
- [ ] `search_aact_trials` queries AACT database with eligibility text search (when credentials configured)
- [ ] `get_trial_details_combined` merges data from both ClinicalTrials.gov and NCI
- [ ] Existing `clinical_trials.py` plugin continues to work unchanged
- [ ] ClinicalTrials agent instructions reference the new MCP tools

## Implementation Phases

### MVP (build now)
- `search_nci_gyn_trials` — NCI API (no auth required)
- `get_gog_nrg_trials` — ClinicalTrials.gov filtered search (no auth required)
- `get_trial_details_combined` — combined details (no auth required)
- Mount in `mcp_app.py`

### V2 (later, requires AACT account)
- `search_aact_trials` — AACT PostgreSQL (requires registration at https://aact.ctti-clinicaltrials.org/)
- Add `asyncpg` dependency

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-03-12-clinical-trials-mcp-server-brainstorm.md](docs/brainstorms/2026-03-12-clinical-trials-mcp-server-brainstorm.md)
- Existing plugin: `src/scenarios/default/tools/clinical_trials.py`
- Existing MCP app: `src/mcp_app.py`
- NCI API: https://clinicaltrialsapi.cancer.gov/api/v2
- ClinicalTrials.gov API: https://clinicaltrials.gov/api/v2/studies
- AACT: https://aact.ctti-clinicaltrials.org/
