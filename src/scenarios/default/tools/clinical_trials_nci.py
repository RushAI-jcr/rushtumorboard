# SK Plugin bridge for NCI/GOG/AACT clinical trial search tools.
#
# Wraps the core functions from clinical_trials_mcp.py as Semantic Kernel
# @kernel_function() methods so the ClinicalTrials agent can call them directly.

import logging

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration
from mcp_servers.clinical_trials_mcp import (
    aact_search,
    gog_nrg_search,
    nci_search,
    trial_details_combined,
)

logger = logging.getLogger(__name__)


def create_plugin(plugin_config: PluginConfiguration):
    return ClinicalTrialsNCIPlugin()


class ClinicalTrialsNCIPlugin:

    @kernel_function(
        description="Search NCI Cancer Clinical Trials API for GYN oncology trials. "
        "Supports filtering by cancer type, biomarkers, phase, and status."
    )
    async def search_nci_gyn_trials(
        self,
        cancer_type: str,
        biomarker: str = "",
        phase: str = "",
        status: str = "active",
    ) -> str:
        """Search NCI for GYN oncology trials.

        Args:
            cancer_type: GYN cancer type (ovarian, endometrial, cervical, vulvar, vaginal, fallopian, peritoneal, gtd)
            biomarker: Optional biomarker filter (e.g., BRCA1, HRD, MSI-H, PD-L1, HER2)
            phase: Optional trial phase (I, II, III, I_II)
            status: Trial status (default: active)
        """
        return await nci_search(cancer_type, biomarker, phase, status)

    @kernel_function(
        description="Search for GOG/NRG Oncology cooperative group trials for GYN cancers."
    )
    async def get_gog_nrg_trials(
        self,
        cancer_type: str,
        status: str = "RECRUITING",
    ) -> str:
        """Search for GOG/NRG cooperative group trials.

        Args:
            cancer_type: GYN cancer type (ovarian, endometrial, cervical, vulvar)
            status: Trial status filter (default: RECRUITING)
        """
        return await gog_nrg_search(cancer_type, status)

    @kernel_function(
        description="Get comprehensive details about a clinical trial by NCT ID, "
        "combining data from ClinicalTrials.gov and NCI APIs."
    )
    async def get_trial_details_combined(self, nct_id: str) -> str:
        """Get detailed trial information from multiple sources.

        Args:
            nct_id: The NCT identifier (e.g., NCT12345678)
        """
        return await trial_details_combined(nct_id)

    @kernel_function(
        description="Search AACT database for clinical trials with eligibility criteria filtering. "
        "Requires AACT credentials (AACT_USER, AACT_PASSWORD env vars)."
    )
    async def search_aact_trials(
        self,
        condition: str,
        eligibility_keywords: str = "",
        intervention: str = "",
        status: str = "Recruiting",
        limit: int = 20,
    ) -> str:
        """Search AACT PostgreSQL database for trials.

        Args:
            condition: Cancer condition (e.g., 'ovarian cancer')
            eligibility_keywords: Keywords for eligibility text (e.g., 'BRCA', 'platinum resistant')
            intervention: Optional drug/intervention filter
            status: Trial status (default: Recruiting)
            limit: Max results (default: 20, max: 100)
        """
        return await aact_search(condition, eligibility_keywords, intervention, status, limit)
