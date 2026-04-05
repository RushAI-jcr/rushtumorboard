# Radiology Report Extraction Tool for GYN Oncology Tumor Board
#
# Extracts structured radiology findings from Epic report text using LLM.
# Replaces the CXR deep learning model — uses LLM to interpret radiology
# report narratives for CT, MRI, PET/CT, and ultrasound.

import json

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

from .medical_report_extractor import MedicalReportExtractorBase
from .note_type_constants import (
    ADDENDUM_TYPES, ASSESSMENT_PLAN_TYPES, EXTERNAL_TYPES,
    GENERAL_CLINICAL_TYPES, ONCOLOGY_TIER_A_TYPES,
)
from .validation import validate_patient_id

RADIOLOGY_SYSTEM_PROMPT = """
    You are a gynecologic oncology radiology specialist. Extract structured findings
    from the following imaging report(s). Return a JSON object with these fields:

    {
        "studies": [
            {
                "modality": "CT/MRI/PET-CT/Ultrasound/CXR",
                "study_name": "full study name (e.g., CT CAP, MRI Pelvis, PET/CT, TVUS, CT Angio Chest)",
                "study_date": "date in M/D/YY format",
                "osh_origin": "true if from outside hospital, false otherwise",
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
                "other_findings": "ANY additional clinically significant findings: PE, pleural effusions, hydropneumothorax, SBO, fistula, hydronephrosis, stents, consolidation, etc. These are CRITICAL for the tumor board.",
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
                "impression": "CRITICAL: Copy the radiologist's IMPRESSION/CONCLUSION section verbatim or near-verbatim. This is the most important field. If the report has an 'IMPRESSION:' section, extract it completely. If no formal impression section exists, synthesize the key conclusions from the findings."
            }
        ],
        "longitudinal_summary": "Brief narrative comparing findings across studies if multiple reports — note disease trajectory (responding, stable, progressing, new sites)",
        "disease_burden_assessment": "overall assessment of disease extent"
    }

    CRITICAL RULES:
    1. The "impression" field is THE MOST IMPORTANT field. Extract the full radiologist impression.
    2. Include ALL studies found — do not skip or summarize older studies. The tumor board needs complete imaging history.
    3. Include clinically significant non-cancer findings (PE, pleural effusions, SBO, fistulas, hydronephrosis, etc.).
    4. Preserve specific measurements (cm, mm) exactly as stated in the reports.
    5. Note comparison findings explicitly: "interval increased", "stable", "new", "decreased".
    6. If a field is not mentioned in the report, use "not reported" or null.
    7. Only include information explicitly stated in the reports.
    8. CHRONOLOGICAL ORDER IS MANDATORY: oldest study_date first, most recent last.
    9. For RECIST: calculate percent change as ((current - prior) / prior * 100).
       CR = complete resolution, PR = >=30% decrease, PD = >=20% increase, SD = neither.
"""


def create_plugin(plugin_config: PluginConfiguration):
    return RadiologyExtractorPlugin(plugin_config)


class RadiologyExtractorPlugin(MedicalReportExtractorBase):
    report_type = "radiology"
    accessor_method = "get_radiology_reports"
    system_prompt = RADIOLOGY_SYSTEM_PROMPT
    error_key = "studies"

    # Layer 2: Tier A oncology notes (imaging often summarized in oncology consults,
    # especially for OSH patients) + external/OSH unmapped notes.
    layer2_note_types: tuple[str, ...] = ONCOLOGY_TIER_A_TYPES + EXTERNAL_TYPES
    # Layer 3: General notes where physicians summarize imaging findings.
    # Confirmed NoteTypes in real Rush Epic Clarity exports.
    layer3_note_types: tuple[str, ...] = (
        GENERAL_CLINICAL_TYPES + ASSESSMENT_PLAN_TYPES
        + ("Multidisciplinary Tumor Board",) + ADDENDUM_TYPES
    )
    layer3_keywords = (
        "ct scan", "ct chest", "ct abdomen", "ct pelvis", "ct a/p", "ct cap",
        "mri", "mri pelvis", "mri abdomen",
        "pet", "pet-ct", "pet/ct", "suv",
        "ultrasound", "transvaginal", "tvus",
        "imaging", "radiolog",
        "recist", "lesion", "mass", "tumor", "nodule",
        "ascites", "peritoneal", "omental", "lymph node",
        # Additional imaging modalities
        "x-ray", "xray", "cxr", "chest x-ray", "bone scan", "mammogram", "dexa",
        # OSH imaging
        "outside imaging", "osh", "prior imaging", "outside hospital",
    )

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
        if not validate_patient_id(patient_id):
            return json.dumps({"error": "Invalid patient ID."})
        return await self._extract(patient_id)
