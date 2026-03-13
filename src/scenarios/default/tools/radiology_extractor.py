# Radiology Report Extraction Tool for GYN Oncology Tumor Board
#
# Extracts structured radiology findings from Epic report text using LLM.
# Replaces the CXR deep learning model — uses LLM to interpret radiology
# report narratives for CT, MRI, PET/CT, and ultrasound.

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

from .medical_report_extractor import MedicalReportExtractorBase

RADIOLOGY_SYSTEM_PROMPT = """
    You are a gynecologic oncology radiology specialist. Extract structured findings
    from the following imaging report(s). Return a JSON object with these fields:

    {
        "studies": [
            {
                "modality": "CT/MRI/PET-CT/Ultrasound",
                "study_name": "full study name",
                "study_date": "date",
                "indication": "clinical indication",
                "comparison": "prior study compared to, if any",
                "primary_tumor": {
                    "location": "anatomic location",
                    "measurements_cm": "dimensions (AP x TR x CC)",
                    "description": "morphologic description",
                    "change_from_prior": "new/stable/increased/decreased with details"
                },
                "lymph_nodes": {
                    "pelvic": "description with measurements",
                    "para_aortic": "description with measurements",
                    "inguinal": "description if applicable",
                    "other": "any other nodal findings"
                },
                "peritoneal_disease": {
                    "present": true/false,
                    "locations": ["omentum", "mesentery", "diaphragm", etc.],
                    "description": "details of carcinomatosis/implants",
                    "pci_estimate": "peritoneal carcinomatosis index if estimable"
                },
                "ascites": {
                    "present": true/false,
                    "volume": "small/moderate/large",
                    "description": "distribution details"
                },
                "distant_metastases": {
                    "liver": "description or absent",
                    "lung": "description or absent",
                    "bone": "description or absent",
                    "brain": "description or absent",
                    "other": "any other metastatic sites"
                },
                "other_findings": "any additional relevant findings",
                "recist_measurements": {
                    "target_lesions": [
                        {
                            "location": "anatomic site",
                            "current_measurement_cm": number,
                            "prior_measurement_cm": number,
                            "change_percent": number
                        }
                    ],
                    "sum_of_diameters_cm": number,
                    "prior_sum_cm": number,
                    "overall_response": "CR/PR/SD/PD or not assessed"
                },
                "impression": "radiologist's impression/conclusion"
            }
        ],
        "longitudinal_summary": "Brief narrative comparing findings across studies if multiple reports",
        "disease_burden_assessment": "overall assessment of disease extent"
    }

    If a field is not mentioned in the report, use "not reported" or null.
    Only include information explicitly stated in the reports.
    For RECIST: calculate percent change as ((current - prior) / prior * 100).
    CR = complete resolution, PR = >=30% decrease, PD = >=20% increase, SD = neither.
"""


def create_plugin(plugin_config: PluginConfiguration):
    return RadiologyExtractorPlugin(plugin_config)


class RadiologyExtractorPlugin(MedicalReportExtractorBase):
    report_type = "radiology"
    accessor_method = "get_radiology_reports"
    fallback_note_type = "radiology"
    system_prompt = RADIOLOGY_SYSTEM_PROMPT
    error_key = "studies"

    @kernel_function(
        description="Extract structured radiology findings from a patient's imaging reports. "
        "Summarizes tumor measurements, lymph nodes, peritoneal disease, ascites, "
        "metastases, and RECIST response if applicable."
    )
    async def extract_radiology_findings(self, patient_id: str) -> str:
        """Extract structured radiology findings from Epic radiology reports using LLM.

        Args:
            patient_id: The patient ID to retrieve radiology reports for.

        Returns:
            Structured JSON with radiology findings.
        """
        return await self._extract(patient_id)
