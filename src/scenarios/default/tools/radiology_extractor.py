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
                "modality": "CT/MRI/PET-CT/FDG-PET/Ultrasound/TVUS/CXR/Bone Scan/Nuclear Medicine",
                "study_name": "full study name (e.g., CT CAP, MRI Pelvis, PET/CT, TVUS, CT Angio Chest)",
                "study_date": "date in M/D/YY format",
                "osh_origin": "true if from outside hospital, false otherwise",
                "status": "completed/pending (default: completed)",
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
    10. If imaging was performed at an outside hospital (OSH), set osh_origin to true.
        Look for: "outside hospital", "OSH", "external facility", "transferred from",
        "records from [hospital]", "imaging from [hospital]". Include institution name
        in study_name if mentioned.
    11. Physicians often summarize outside imaging in clinical notes: "outside CT showed...",
        "PET from OSH demonstrated...", "per report from [hospital]...". Extract these
        with the same rigor as dedicated radiology reports.
    12. If imaging is described as "scheduled", "ordered", or "pending", extract it with
        status="pending" and include the scheduled date if mentioned. Example:
        {"study_name": "Lymphangiogram", "date": "3/13/26", "status": "pending",
         "findings": "Scheduled, results not yet available"}
    13. Rush Copley is a Rush affiliate — do NOT flag Copley imaging as OSH.
        Only flag as OSH when imaging is from non-Rush institutions (Riverside, Lutheran,
        Good Samaritan/GSH, Edwards, or explicitly labeled "outside hospital"/"OSH").
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
        # CT variants
        "ct scan", "ct chest", "ct abdomen", "ct pelvis", "ct a/p", "ct cap",
        "ct angiography", "ct angio", "cta", "ct enterography", "ct w/wo",
        # MRI variants
        "mri", "mri pelvis", "mri abdomen", "mr pelvis", "mri brain", "mri spine",
        # PET variants (high-miss-risk — often only in oncology notes)
        "pet", "pet-ct", "pet/ct", "suv", "fdg", "fdg-pet", "fdg pet", "fdg avid",
        # Ultrasound variants (high-miss-risk — often only in GYN notes)
        "ultrasound", "transvaginal", "tvus", "transvaginal us", "endovaginal",
        "pelvic ultrasound", "pelvic us", "renal ultrasound", "renal us", "doppler",
        # General imaging terms
        "imaging", "radiolog",
        "recist", "lesion", "mass", "tumor", "nodule",
        "ascites", "peritoneal", "omental", "lymph node",
        # Additional imaging modalities
        "x-ray", "xray", "cxr", "chest x-ray", "bone scan", "mammogram", "dexa",
        "nuclear medicine", "lymphoscintigraphy",
        # OSH imaging (expanded — catches referral language)
        "outside imaging", "osh", "prior imaging", "outside hospital",
        "outside facility", "external facility", "outside institution",
        "referring hospital", "transferred from", "records from",
        # CT variants — March 11 gap fills
        "ct ap",          # no-slash variant of "ct a/p" — common in handouts
        "ct rp",          # CT retroperitoneum
        "ct cap w",       # CT CAP with contrast
        "ctap",           # no-space variant
        # Ultrasound variants — March 11 gap fills
        "us pelvis",      # reversed word order of "pelvic us"
        "tv us",          # space-separated variant of "tvus"
        # MRI variants — March 11 gap fills
        "pelvic mri",     # reversed word order of "mri pelvis"
        "mri ap",         # MRI abdomen/pelvis
        # Additional modalities — March 11 gap fills
        "lymphangiogram", # rare but clinically significant (vulvar cancer workups)
        # Pending/scheduled imaging keywords
        "scheduled", "ordered", "pending",
        # Named OSH hospitals (supplement generic OSH keywords)
        "riverside", "lutheran", "good samaritan", "edwards",
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
