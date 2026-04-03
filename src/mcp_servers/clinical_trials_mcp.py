# Clinical Trials MCP Server for GYN Oncology Tumor Board
#
# Provides supplementary clinical trial search tools via MCP protocol.
# Works alongside the existing clinical_trials.py Semantic Kernel plugin.
#
# Core search functions are exposed at module level so they can be called
# directly from SK plugins (via clinical_trials_nci.py) as well as MCP tools.
#
# Data Sources:
#   - NCI Cancer Clinical Trials API (https://clinicaltrialsapi.cancer.gov/api/v2)
#   - ClinicalTrials.gov API v2 (for GOG/NRG filtered search)
#   - AACT PostgreSQL database (optional, requires registration)

import asyncio
import json
import logging
import os
import uuid
from typing import Any

import aiohttp
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# GYN cancer type mappings for NCI API
NCI_DISEASE_MAP = {
    "ovarian": "Ovarian Cancer",
    "ovary": "Ovarian Cancer",
    "endometrial": "Endometrial Cancer",
    "endometrium": "Endometrial Cancer",
    "uterine": "Uterine Cancer",
    "cervical": "Cervical Cancer",
    "cervix": "Cervical Cancer",
    "vulvar": "Vulvar Cancer",
    "vulva": "Vulvar Cancer",
    "vaginal": "Vaginal Cancer",
    "fallopian": "Fallopian Tube Cancer",
    "fallopian tube": "Fallopian Tube Cancer",
    "peritoneal": "Primary Peritoneal Cancer",
    "primary peritoneal": "Primary Peritoneal Cancer",
    "gtd": "Gestational Trophoblastic Disease",
    "gtn": "Gestational Trophoblastic Neoplasia",
    "choriocarcinoma": "Choriocarcinoma",
    "vagina": "Vaginal Cancer",
    "hydatidiform mole": "Gestational Trophoblastic Disease",
    "molar pregnancy": "Gestational Trophoblastic Disease",
    "uterine sarcoma": "Uterine Sarcoma",
    "leiomyosarcoma": "Uterine Leiomyosarcoma",
}

# ClinicalTrials.gov condition search terms
CTG_CONDITION_MAP = {
    "ovarian": "ovarian cancer",
    "ovary": "ovarian cancer",
    "endometrial": "endometrial cancer",
    "endometrium": "endometrial cancer",
    "uterine": "uterine cancer",
    "cervical": "cervical cancer",
    "cervix": "cervical cancer",
    "vulvar": "vulvar cancer",
    "vulva": "vulvar cancer",
    "vaginal": "vaginal cancer",
    "fallopian": "fallopian tube cancer",
    "fallopian tube": "fallopian tube cancer",
    "peritoneal": "peritoneal cancer",
    "primary peritoneal": "primary peritoneal cancer",
    "gtd": "gestational trophoblastic",
    "gtn": "gestational trophoblastic neoplasia",
    "choriocarcinoma": "choriocarcinoma",
    "vagina": "vaginal cancer",
    "hydatidiform mole": "hydatidiform mole",
    "molar pregnancy": "molar pregnancy",
    "uterine sarcoma": "uterine sarcoma",
    "leiomyosarcoma": "uterine leiomyosarcoma",
}

NCI_API_BASE = "https://clinicaltrialsapi.cancer.gov/api/v2"
CTG_API_BASE = "https://clinicaltrials.gov/api/v2/studies"


def _get_nci_headers() -> dict:
    """Get headers for NCI API requests, including API key if configured."""
    headers = {}
    nci_api_key = os.getenv("NCI_API_KEY")
    if nci_api_key:
        headers["X-API-KEY"] = nci_api_key
    return headers


# Shared aiohttp session (lazy init, protected by lock)
_http_session: aiohttp.ClientSession | None = None
_session_lock: asyncio.Lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    """Get or create a shared aiohttp session with timeout (thread-safe)."""
    global _http_session
    if _http_session is not None and not _http_session.closed:
        return _http_session
    async with _session_lock:
        if _http_session is None or _http_session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            _http_session = aiohttp.ClientSession(timeout=timeout)
    return _http_session


# ============================================================================
# Core search functions (callable from both MCP tools and SK plugins)
# ============================================================================


async def nci_search(
    cancer_type: str,
    biomarker: str = "",
    phase: str = "",
    status: str = "active",
) -> str:
    """Search NCI Cancer Clinical Trials API for GYN oncology trials."""
    disease = NCI_DISEASE_MAP.get(cancer_type.lower(), cancer_type)

    params = {
        "diseases.name._fulltext": disease,
        "current_trial_status": status,
        "size": 25,
        "include": "nct_id,brief_title,phase,lead_org,principal_investigator,"
                   "current_trial_status,diseases,biomarkers,arms,eligibility,"
                   "brief_summary",
    }

    if biomarker:
        params["biomarkers.name._fulltext"] = biomarker

    if phase:
        params["phase.phase"] = phase

    try:
        session = await _get_session()
        async with session.get(f"{NCI_API_BASE}/trials", params=params, headers=_get_nci_headers()) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error("NCI API error %d: %s", resp.status, error_text)
                return json.dumps({
                    "error": f"NCI API returned status {resp.status}",
                    "total": 0,
                    "trials": []
                })
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        ref = uuid.uuid4().hex[:8]
        logger.error("NCI API connection error [ref=%s]: %s", ref, e)
        return json.dumps({"error": f"NCI API connection error. Reference: {ref}", "total": 0, "trials": []})

    if not isinstance(data, dict):
        return json.dumps({"error": "Unexpected API response format", "total": 0, "trials": []})

    trials = []
    for trial in data.get("data", []):
        trial_info = {
            "nct_id": trial.get("nct_id", ""),
            "title": trial.get("brief_title", ""),
            "phase": trial.get("phase", {}).get("phase", "N/A") if isinstance(trial.get("phase"), dict) else str(trial.get("phase", "N/A")),
            "status": trial.get("current_trial_status", ""),
            "lead_organization": trial.get("lead_org", ""),
            "principal_investigator": trial.get("principal_investigator", ""),
            "diseases": [d.get("name", "") for d in trial.get("diseases", []) if d.get("name")],
            "biomarkers": [b.get("name", "") for b in trial.get("biomarkers", []) if b.get("name")],
            "brief_summary": trial.get("brief_summary", "")[:500],
            "url": f"https://clinicaltrials.gov/study/{trial.get('nct_id', '')}",
        }

        # Extract arms/interventions
        arms = trial.get("arms", [])
        if arms:
            trial_info["interventions"] = []
            for arm in arms[:4]:
                for intervention in arm.get("interventions", []):
                    name = intervention.get("intervention_name", "")
                    if name and name not in trial_info["interventions"]:
                        trial_info["interventions"].append(name)

        trials.append(trial_info)

    result = {
        "total": data.get("total", len(trials)),
        "source": "NCI Cancer Clinical Trials API",
        "cancer_type_searched": disease,
        "trials": trials,
    }

    logger.info("NCI search for '%s' returned %d trials", disease, len(trials))
    return json.dumps(result, indent=2)


async def gog_nrg_search(
    cancer_type: str,
    status: str = "RECRUITING",
) -> str:
    """Search for GOG/NRG Oncology cooperative group trials."""
    condition = CTG_CONDITION_MAP.get(cancer_type.lower(), cancer_type)

    search_term = (
        f'("{condition}") AND '
        f'(GOG OR NRG OR "NRG Oncology" OR "Gynecologic Oncology Group" OR '
        f'"GOG Foundation" OR "GOG Partners")'
    )

    params = {
        "query.term": search_term,
        "filter.overallStatus": status,
        "pageSize": 25,
        "fields": "IdentificationModule|ConditionsModule|DesignModule|"
                  "SponsorCollaboratorsModule|StatusModule|DescriptionModule",
    }

    try:
        session = await _get_session()
        async with session.get(CTG_API_BASE, params=params) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error("ClinicalTrials.gov API error %d: %s", resp.status, error_text)
                return json.dumps({
                    "error": f"ClinicalTrials.gov API returned status {resp.status}",
                    "total": 0,
                    "trials": []
                })
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        ref = uuid.uuid4().hex[:8]
        logger.error("ClinicalTrials.gov API connection error [ref=%s]: %s", ref, e)
        return json.dumps({"error": f"ClinicalTrials.gov API connection error. Reference: {ref}", "total": 0, "trials": []})

    trials = []
    for study in data.get("studies", []):
        protocol = study.get("protocolSection", {})
        id_mod = protocol.get("identificationModule", {})
        design = protocol.get("designModule", {})
        sponsors = protocol.get("sponsorCollaboratorsModule", {})
        status_mod = protocol.get("statusModule", {})
        desc_mod = protocol.get("descriptionModule", {})

        lead_sponsor = sponsors.get("leadSponsor", {}).get("name", "")
        collaborators = [c.get("name", "") for c in sponsors.get("collaborators", [])]

        all_orgs = [lead_sponsor] + collaborators
        is_gog_nrg = any(
            org_name for org_name in all_orgs
            if any(term in org_name.upper() for term in ["GOG", "NRG", "GYNECOLOGIC ONCOLOGY GROUP"])
        )

        trial_info = {
            "nct_id": id_mod.get("nctId", ""),
            "title": id_mod.get("briefTitle", ""),
            "official_title": id_mod.get("officialTitle", ""),
            "phase": design.get("phases", []),
            "status": status_mod.get("overallStatus", ""),
            "lead_sponsor": lead_sponsor,
            "collaborators": collaborators,
            "is_gog_nrg": is_gog_nrg,
            "brief_summary": desc_mod.get("briefSummary", "")[:500],
            "url": f"https://clinicaltrials.gov/study/{id_mod.get('nctId', '')}",
        }
        trials.append(trial_info)

    result = {
        "total": len(trials),
        "source": "ClinicalTrials.gov (GOG/NRG filtered)",
        "cancer_type_searched": condition,
        "trials": trials,
    }

    logger.info("GOG/NRG search for '%s' returned %d trials", condition, len(trials))
    return json.dumps(result, indent=2)


async def trial_details_combined(nct_id: str) -> str:
    """Get detailed trial information from ClinicalTrials.gov + NCI APIs."""
    nct_id = nct_id.strip().upper()
    if not nct_id.startswith("NCT"):
        nct_id = f"NCT{nct_id}"

    combined: dict[str, Any] = {
        "nct_id": nct_id,
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
    }

    session = await _get_session()

    async def fetch_ctg() -> Any:
        try:
            async with session.get(f"{CTG_API_BASE}/{nct_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"_error": f"Status {resp.status}"}
        except aiohttp.ClientError as e:
            return {"_error": str(e)}

    async def fetch_nci() -> Any:
        try:
            async with session.get(f"{NCI_API_BASE}/trials/{nct_id}", headers=_get_nci_headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except aiohttp.ClientError:
            return None

    ctg_result, nci_result = await asyncio.gather(fetch_ctg(), fetch_nci())

    if isinstance(ctg_result, dict) and "_error" not in ctg_result:
        protocol = ctg_result.get("protocolSection", {})
        id_mod = protocol.get("identificationModule", {})
        desc_mod = protocol.get("descriptionModule", {})
        elig_mod = protocol.get("eligibilityModule", {})
        design_mod = protocol.get("designModule", {})
        arms_mod = protocol.get("armsInterventionsModule", {})
        status_mod = protocol.get("statusModule", {})
        conditions_mod = protocol.get("conditionsModule", {})

        combined["title"] = id_mod.get("briefTitle", "")
        combined["official_title"] = id_mod.get("officialTitle", "")
        combined["brief_summary"] = desc_mod.get("briefSummary", "")
        combined["detailed_description"] = desc_mod.get("detailedDescription", "")[:1000]
        combined["status"] = status_mod.get("overallStatus", "")
        combined["phase"] = design_mod.get("phases", [])
        combined["conditions"] = conditions_mod.get("conditions", [])
        combined["eligibility_criteria"] = elig_mod.get("eligibilityCriteria", "")
        combined["min_age"] = elig_mod.get("minimumAge", "")
        combined["max_age"] = elig_mod.get("maximumAge", "")
        combined["sex"] = elig_mod.get("sex", "")
        arms = arms_mod.get("armGroups", [])
        combined["arms"] = [
            {
                "label": arm.get("label", ""),
                "type": arm.get("type", ""),
                "description": arm.get("description", "")[:300],
                "interventions": arm.get("interventionNames", []),
            }
            for arm in arms
        ]
    elif isinstance(ctg_result, dict):
        combined["clinicaltrials_gov_error"] = ctg_result.get("_error", "Unknown error")

    if nci_result:
        trial = nci_result.get("data", nci_result)
        combined["nci_diseases"] = [
            {"name": d.get("name", ""), "type": d.get("type", "")}
            for d in trial.get("diseases", [])
        ]
        combined["nci_biomarkers"] = [
            {
                "name": b.get("name", ""),
                "assay_purpose": b.get("assay_purpose", ""),
                "inclusion_indicator": b.get("inclusion_indicator", ""),
            }
            for b in trial.get("biomarkers", [])
        ]
        combined["lead_org"] = trial.get("lead_org", "")
        combined["principal_investigator"] = trial.get("principal_investigator", "")

    logger.info("Combined details fetched for %s", nct_id)
    return json.dumps(combined, indent=2, default=str)


async def study_statistics(condition: str) -> str:
    """Get trial count statistics for a condition from ClinicalTrials.gov."""
    session = await _get_session()

    status_buckets = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED", "NOT_YET_RECRUITING"]
    results: dict[str, int] = {}

    async def fetch_count(status: str) -> tuple[str, int]:
        params = {
            "query.cond": condition,
            "filter.overallStatus": status,
            "pageSize": 1,
            "countTotal": "true",
        }
        try:
            async with session.get(CTG_API_BASE, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return status, data.get("totalCount", 0)
                return status, 0
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return status, 0

    counts = await asyncio.gather(*[fetch_count(s) for s in status_buckets])
    for status, count in counts:
        results[status.lower()] = count

    total = sum(results.values())
    result = {
        "condition": condition,
        "source": "ClinicalTrials.gov API v2",
        "total_in_snapshot": total,
        "by_status": results,
    }
    logger.info("Study statistics for '%s': %d total", condition, total)
    return json.dumps(result, indent=2)


async def keyword_search(
    keyword: str,
    status: str = "RECRUITING",
    page_size: int = 20,
) -> str:
    """General free-text keyword search against ClinicalTrials.gov v2 API."""
    page_size = min(max(page_size, 1), 50)

    params = {
        "query.term": keyword,
        "filter.overallStatus": status,
        "pageSize": page_size,
        "fields": "IdentificationModule|ConditionsModule|DesignModule|"
                  "SponsorCollaboratorsModule|StatusModule|DescriptionModule",
        "countTotal": "true",
    }

    try:
        session = await _get_session()
        async with session.get(CTG_API_BASE, params=params) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error("CTG keyword search error %d: %s", resp.status, error_text)
                return json.dumps({"error": f"ClinicalTrials.gov API returned status {resp.status}", "total": 0, "trials": []})
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        ref = uuid.uuid4().hex[:8]
        logger.error("CTG keyword search connection error [ref=%s]: %s", ref, e)
        return json.dumps({"error": f"ClinicalTrials.gov API connection error. Reference: {ref}", "total": 0, "trials": []})

    trials = []
    for study in data.get("studies", []):
        protocol = study.get("protocolSection", {})
        id_mod = protocol.get("identificationModule", {})
        conditions_mod = protocol.get("conditionsModule", {})
        design_mod = protocol.get("designModule", {})
        status_mod = protocol.get("statusModule", {})
        desc_mod = protocol.get("descriptionModule", {})
        sponsors = protocol.get("sponsorCollaboratorsModule", {})

        trials.append({
            "nct_id": id_mod.get("nctId", ""),
            "title": id_mod.get("briefTitle", ""),
            "conditions": conditions_mod.get("conditions", []),
            "phase": design_mod.get("phases", []),
            "status": status_mod.get("overallStatus", ""),
            "lead_sponsor": sponsors.get("leadSponsor", {}).get("name", ""),
            "brief_summary": desc_mod.get("briefSummary", "")[:500],
            "url": f"https://clinicaltrials.gov/study/{id_mod.get('nctId', '')}",
        })

    result = {
        "total": data.get("totalCount", len(trials)),
        "returned": len(trials),
        "source": "ClinicalTrials.gov API v2",
        "keyword": keyword,
        "status_filter": status,
        "trials": trials,
    }
    logger.info("Keyword search '%s' returned %d/%d trials", keyword, len(trials), result["total"])
    return json.dumps(result, indent=2)


async def aact_search(
    condition: str,
    eligibility_keywords: str = "",
    intervention: str = "",
    status: str = "Recruiting",
    limit: int = 20,
) -> str:
    """Search AACT PostgreSQL database for trials."""
    aact_user = os.getenv("AACT_USER")
    aact_password = os.getenv("AACT_PASSWORD")

    if not aact_user or not aact_password:
        return json.dumps({
            "error": "AACT credentials not configured. Set AACT_USER and AACT_PASSWORD environment variables. "
                     "Register at https://aact.ctti-clinicaltrials.org/ for free access.",
            "total": 0,
            "trials": [],
        })

    try:
        import asyncpg
    except ImportError:
        return json.dumps({
            "error": "asyncpg not installed. Run: pip install asyncpg",
            "total": 0,
            "trials": [],
        })

    # Clamp limit to prevent abuse
    limit = min(max(limit, 1), 100)

    conn = None
    try:
        conn = await asyncpg.connect(
            host=os.getenv("AACT_HOST", "aact-db.ctti-clinicaltrials.org"),
            port=int(os.getenv("AACT_PORT", "5432")),
            database="aact",
            user=aact_user,
            password=aact_password,
        )

        query = """
            SELECT DISTINCT s.nct_id, s.brief_title, s.overall_status, s.phase,
                   s.start_date, s.enrollment, e.criteria
            FROM ctgov.studies s
            JOIN ctgov.eligibilities e ON s.nct_id = e.nct_id
            JOIN ctgov.conditions c ON s.nct_id = c.nct_id
            WHERE s.overall_status = $1
              AND c.name ILIKE $2
        """
        params: list[str | int] = [status, f"%{condition}%"]
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

        query += f" ORDER BY s.start_date DESC NULLS LAST LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(query, *params)

        trials = []
        for r in rows:
            trial = dict(r)
            for k, v in trial.items():
                if hasattr(v, "isoformat"):
                    trial[k] = v.isoformat()
            trial["url"] = f"https://clinicaltrials.gov/study/{trial.get('nct_id', '')}"
            if trial.get("criteria"):
                trial["criteria"] = trial["criteria"][:2000]
            trials.append(trial)

        result = {
            "total": len(trials),
            "source": "AACT Database (ClinicalTrials.gov mirror)",
            "condition_searched": condition,
            "eligibility_filter": eligibility_keywords or "none",
            "trials": trials,
        }

        logger.info("AACT search for '%s' (keywords='%s') returned %d trials", condition, eligibility_keywords, len(trials))
        return json.dumps(result, indent=2)

    except Exception as e:
        ref = uuid.uuid4().hex[:8]
        logger.error("AACT query error [ref=%s]: %s", ref, e)
        return json.dumps({
            "error": f"AACT database error. Reference: {ref}",
            "total": 0,
            "trials": [],
        })
    finally:
        if conn:
            await conn.close()


# ============================================================================
# MCP Server (thin wrappers around core functions)
# ============================================================================


def create_clinical_trials_mcp() -> FastMCP:
    """Create and return the Clinical Trials MCP server instance."""

    mcp = FastMCP("clinical-trials-gyn")

    @mcp.tool(
        description="Search NCI Cancer Clinical Trials API for GYN oncology trials. "
        "Returns trials from the National Cancer Institute including GOG/NRG cooperative group trials. "
        "Supports filtering by GYN cancer type, biomarkers, phase, and status."
    )
    async def search_nci_gyn_trials(
        cancer_type: str,
        biomarker: str = "",
        phase: str = "",
        status: str = "active",
    ) -> str:
        return await nci_search(cancer_type, biomarker, phase, status)

    @mcp.tool(
        description="Search specifically for GOG/NRG Oncology cooperative group trials for GYN cancers. "
        "GOG (Gynecologic Oncology Group) and NRG Oncology run the major cooperative group trials "
        "in gynecologic oncology."
    )
    async def get_gog_nrg_trials(
        cancer_type: str,
        status: str = "RECRUITING",
    ) -> str:
        return await gog_nrg_search(cancer_type, status)

    @mcp.tool(
        description="Get comprehensive details about a specific clinical trial by NCT ID. "
        "Combines data from both ClinicalTrials.gov and NCI Cancer Trials API for a complete picture."
    )
    async def get_trial_details_combined(nct_id: str) -> str:
        return await trial_details_combined(nct_id)

    @mcp.tool(
        description="Search the AACT database for clinical trials with complex eligibility criteria filtering. "
        "AACT mirrors ClinicalTrials.gov in a PostgreSQL database, enabling full-text search on eligibility criteria. "
        "Requires AACT credentials (register at https://aact.ctti-clinicaltrials.org/). "
        "Returns trials matching condition and eligibility keyword filters."
    )
    async def search_aact_trials(
        condition: str,
        eligibility_keywords: str = "",
        intervention: str = "",
        status: str = "Recruiting",
        limit: int = 20,
    ) -> str:
        return await aact_search(condition, eligibility_keywords, intervention, status, limit)

    @mcp.tool(
        description="Get clinical trial count statistics for a condition from ClinicalTrials.gov. "
        "Returns total trial counts broken down by status (recruiting, active, completed, not-yet-recruiting). "
        "Useful for understanding the trial landscape for a given disease or condition."
    )
    async def get_study_statistics(condition: str) -> str:
        return await study_statistics(condition)

    @mcp.tool(
        description="General free-text keyword search against ClinicalTrials.gov v2 API. "
        "Unlike the GYN-specific NCI search, this accepts any keyword(s) and returns matching trials across all diseases. "
        "Use for unusual diagnoses, combination queries (e.g. 'BRCA ovarian pembrolizumab'), or non-GYN conditions."
    )
    async def search_trials_by_keyword(
        keyword: str,
        status: str = "RECRUITING",
        page_size: int = 20,
    ) -> str:
        return await keyword_search(keyword, status, page_size)

    @mcp.tool(description="Shutdown hook to close the shared HTTP session.")
    async def cleanup():
        global _http_session
        if _http_session and not _http_session.closed:
            await _http_session.close()
            _http_session = None
        return "Session closed."

    return mcp
