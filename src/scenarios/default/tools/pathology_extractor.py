# Pathology Report Extraction Tool for GYN Oncology Tumor Board
#
# Extracts structured pathology findings from Epic Caboodle reports using LLM.
# Identifies histologic type, grade, IHC panel, molecular classification,
# and other GYN-specific pathology data.

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

from .medical_report_extractor import MedicalReportExtractorBase

PATHOLOGY_SYSTEM_PROMPT = """
    You are a gynecologic oncology pathology specialist. Extract structured findings
    from the following pathology report(s). Return a JSON object with these fields:

    {
        "specimens": [
            {
                "specimen_type": "biopsy/resection/cytology",
                "procedure_name": "procedure name",
                "report_date": "date",
                "histologic_type": "e.g., High-grade serous carcinoma",
                "histologic_subtype": "e.g., solid/transitional pattern",
                "grade": "Grade 1/2/3 or low-grade/high-grade",
                "tumor_size_cm": "size if mentioned",
                "depth_of_invasion": "e.g., >50% myometrial invasion",
                "margins": "positive/negative/close with details",
                "lvsi": "present/absent/not assessed",
                "lymph_nodes": {
                    "total_examined": number,
                    "positive": number,
                    "sentinel_node": "result if applicable",
                    "details": "description"
                },
                "peritoneal_involvement": "present/absent with details",
                "omental_involvement": "present/absent",
                "residual_disease": "R0/optimal (<1cm)/suboptimal (>1cm)"
            }
        ],
        "ihc_panel": {
            "p53": "wild-type/aberrant (overexpression or null)",
            "ER": "positive/negative with % if available",
            "PR": "positive/negative with % if available",
            "WT1": "positive/negative",
            "p16": "diffuse block positive/negative/patchy",
            "napsin_A": "positive/negative",
            "PAX8": "positive/negative",
            "MLH1": "intact/loss",
            "PMS2": "intact/loss",
            "MSH2": "intact/loss",
            "MSH6": "intact/loss",
            "HER2": "0/1+/2+/3+ or FISH result",
            "PD_L1": "CPS score if available",
            "Ki67": "% if available"
        },
        "molecular_results": {
            "BRCA1": "pathogenic variant/VUS/negative/not tested",
            "BRCA2": "pathogenic variant/VUS/negative/not tested",
            "HRD_score": "score and status if available",
            "MSI_status": "MSI-H/MSS/MSI-L/not tested",
            "MMR_status": "proficient/deficient based on IHC",
            "POLE_mutation": "present/absent/not tested",
            "TMB": "mutations/Mb if available",
            "NTRK_fusion": "present/absent/not tested",
            "PIK3CA": "mutation status if available",
            "other_mutations": "any other molecular findings"
        },
        "endometrial_molecular_classification": "POLEmut/MMRd/p53abn/NSMP/not applicable",
        "figo_pathologic_stage": "stage if determinable from pathology",
        "tnm_stage": "pT/pN/pM if available",
        "synoptic_summary": "brief narrative summary of key findings"
    }

    If a field is not mentioned in the report, use "not reported".
    Only include information explicitly stated in the reports.
    For the endometrial molecular classification, apply ProMisE/TCGA criteria:
    - POLEmut: POLE exonuclease domain mutation present
    - MMRd: Loss of MLH1, PMS2, MSH2, or MSH6 by IHC or MSI-H
    - p53abn: Aberrant p53 (overexpression or null pattern)
    - NSMP: No specific molecular profile (none of the above)
    If not an endometrial cancer, set to "not applicable".
"""


def create_plugin(plugin_config: PluginConfiguration):
    return PathologyExtractorPlugin(plugin_config)


class PathologyExtractorPlugin(MedicalReportExtractorBase):
    report_type = "pathology"
    accessor_method = "get_pathology_reports"
    fallback_note_type = "pathology"
    system_prompt = PATHOLOGY_SYSTEM_PROMPT
    error_key = "findings"

    @kernel_function(
        description="Extract structured pathology findings from a patient's pathology reports. "
        "Returns histologic type, grade, margins, IHC panel, molecular results, "
        "and endometrial molecular classification."
    )
    async def extract_pathology_findings(self, patient_id: str) -> str:
        """Extract structured pathology findings from Epic pathology reports using LLM.

        Args:
            patient_id: The patient ID to retrieve pathology reports for.

        Returns:
            Structured JSON with pathology findings.
        """
        return await self._extract(patient_id)
