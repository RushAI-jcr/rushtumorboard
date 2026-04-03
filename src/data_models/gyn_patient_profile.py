# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Pydantic model for GYN oncology patient profile used by clinical trials matching.

This model is used as a @kernel_function parameter — Semantic Kernel auto-generates
a JSON Schema from it for OpenAI tool calling and parses the LLM's JSON response
via model_validate().
"""

from typing import Any

from pydantic import BaseModel, Field


class GynPatientProfile(BaseModel):
    """Structured GYN oncology patient profile for clinical trial eligibility matching.

    Required fields are the minimum needed for any meaningful trial search.
    Optional fields improve matching accuracy when available.
    """

    # --- Required fields ---
    age: str = Field(
        description="Patient age (e.g., '62').",
        max_length=10,
    )
    primary_site: str = Field(
        description="Cancer primary site: ovary, endometrium, cervix, vulva, fallopian tube, or peritoneal.",
        max_length=500,
    )
    histology: str = Field(
        description="Histologic type (e.g., 'high-grade serous carcinoma', 'endometrioid grade 2', 'clear cell').",
        max_length=500,
    )
    figo_stage: str = Field(
        description="FIGO stage (e.g., 'IIIC', 'IVB', 'IA').",
        max_length=50,
    )
    biomarkers: list[str] = Field(
        description=(
            "Positive/actionable biomarkers "
            "(e.g., ['BRCA1 germline mutation', 'HRD-positive', 'PD-L1 CPS 10'])."
        ),
        max_length=20,
    )
    ecog_performance_status: str = Field(
        description="ECOG PS (e.g., '0', '1').",
        max_length=10,
    )
    prior_therapies: str = Field(
        description=(
            "All prior systemic therapies with lines, agents, dates, and best response. "
            "Example: 'Line 1: carboplatin/paclitaxel x6 cycles (1/24-5/24), CR. "
            "Line 2: PLD x4 (9/24-12/24), PD. Prior bevacizumab: yes. Prior PARP: no.'"
        ),
        max_length=2000,
    )

    # --- Optional fields (improve matching accuracy) ---
    platinum_sensitivity: str = Field(
        default="",
        description="Platinum-sensitive (PFI >6 mo), platinum-resistant (PFI 1-6 mo), or platinum-refractory.",
        max_length=500,
    )
    platinum_free_interval: str = Field(
        default="",
        description="Months since last platinum to progression (e.g., '14 months', '4 months').",
        max_length=50,
    )
    molecular_profile: str = Field(
        default="",
        description=(
            "Full molecular profile: BRCA variant, HRD score, MMR/MSI, p53, POLE, "
            "HER2, ER/PR, FRa, TMB, NGS panel results."
        ),
        max_length=500,
    )
    prior_surgeries: str = Field(
        default="",
        description="Surgical history (e.g., 'PDS with TAH/BSO/omentectomy 3/24, R0 resection').",
        max_length=500,
    )
    current_disease_status: str = Field(
        default="",
        description="NED, stable disease, progressive disease, recurrent, or newly diagnosed.",
        max_length=500,
    )
    comorbidities: str = Field(
        default="",
        description=(
            "Relevant comorbidities (e.g., 'CKD stage 3, type 2 diabetes, prior breast cancer 2018, "
            "autoimmune thyroiditis, HIV negative, no hepatitis')."
        ),
        max_length=500,
    )
    current_medications: str = Field(
        default="",
        description=(
            "Current medications that may affect eligibility "
            "(e.g., anticoagulants, systemic steroids >10mg prednisone/day, CYP3A4 inhibitors)."
        ),
        max_length=500,
    )
    grade: str = Field(
        default="",
        description=(
            "Tumor grade (e.g., 'Grade 2', 'high-grade', 'low-grade'). "
            "Critical for endometrial trials (Grade 1-2 vs 3) and ovarian (HGSC vs LGSC)."
        ),
        max_length=50,
    )
    organ_function_labs: str = Field(
        default="",
        description=(
            "Most recent lab values: ANC, platelets, Hgb, creatinine, bilirubin, AST/ALT, albumin. "
            "Almost every trial requires adequate organ function."
        ),
        max_length=500,
    )
    measurable_disease: str = Field(
        default="",
        description=(
            "Whether patient has RECIST 1.1 measurable disease "
            "(e.g., 'Yes, 3.2cm pelvic mass on CT 2/15/26' or 'No measurable disease, CA-125 only')."
        ),
        max_length=500,
    )
    ascites: str = Field(
        default="",
        description=(
            "Ascites status: none, small volume, moderate, or large volume requiring paracentesis. "
            "Some ovarian trials exclude moderate-to-large ascites."
        ),
        max_length=100,
    )
    cns_metastases: str = Field(
        default="",
        description=(
            "CNS metastasis status: none, treated brain mets (stable X months), "
            "or active untreated brain metastases. Most trials exclude active/untreated CNS disease."
        ),
        max_length=100,
    )

    def to_prompt_dict(self) -> dict[str, Any]:
        """Return non-empty fields for LLM prompt serialization."""
        return {k: v for k, v in self.model_dump().items() if v}

    def to_search_dict(self) -> dict[str, Any]:
        """Return fields relevant for search query generation (subset of full profile)."""
        d: dict[str, Any] = {
            "primary_site": self.primary_site,
            "histology": self.histology,
            "figo_stage": self.figo_stage,
            "biomarkers": self.biomarkers,
        }
        if self.platinum_sensitivity:
            d["platinum_sensitivity"] = self.platinum_sensitivity
        if self.current_disease_status:
            d["current_disease_status"] = self.current_disease_status
        if self.prior_therapies:
            # Extract line count for search query context
            d["number_of_prior_lines"] = self.prior_therapies
        return d
