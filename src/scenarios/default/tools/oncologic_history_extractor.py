# Oncologic History Extraction Tool for GYN Oncology Tumor Board
#
# Extracts structured prior oncologic history from clinical notes, especially
# for outside hospital transfer patients (~20-30% of cases).
# Produces a clear timeline: diagnosis, treatments received, reason for referral.

import json
import logging
import textwrap

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

from .medical_report_extractor import MedicalReportExtractorBase, _JSON_FENCE_RE
from .note_type_constants import (
    ADDENDUM_TYPES, CONSULT_NOTE_TYPES, DISCHARGE_TYPES,
    ED_NOTE_TYPES, HP_TYPES, OPERATIVE_TYPES, PROGRESS_NOTE_TYPES,
)
from .validation import validate_patient_id

logger = logging.getLogger(__name__)

ONCOLOGIC_HISTORY_SYSTEM_PROMPT = """
    You are a gynecologic oncology clinical documentation specialist. Your task is
    to extract and structure a patient's prior oncologic history from clinical notes,
    referral letters, H&P notes, and consultation notes.

    This is especially important for TRANSFER PATIENTS from outside hospitals, where
    the prior history may be buried in narrative text from multiple providers.

    Return a JSON object with these fields:

    {
        "referring_institution": "name of outside hospital/clinic if applicable",
        "referring_physician": "name and specialty if mentioned",
        "reason_for_referral": "why the patient is being seen at this institution (e.g., second opinion, clinical trial, progression, surgical expertise, complex case)",

        "initial_diagnosis": {
            "date": "date of original cancer diagnosis",
            "primary_site": "ovary/endometrium/cervix/vulva/fallopian tube/peritoneal",
            "histologic_type": "e.g., high-grade serous carcinoma",
            "grade": "grade if available",
            "figo_stage_at_diagnosis": "original FIGO stage",
            "tnm_stage": "if available",
            "method_of_diagnosis": "biopsy site/type"
        },

        "molecular_profile": {
            "brca_status": "BRCA1/2 status and variant if known",
            "hrd_status": "HRD score/status if available",
            "mmr_msi_status": "MMR IHC and/or MSI results",
            "p53_status": "aberrant/wild-type if available",
            "pole_status": "if tested",
            "other_molecular": "any other molecular/genomic findings"
        },

        "treatment_timeline": [
            {
                "sequence": 1,
                "date_range": "start date - end date",
                "treatment_type": "surgery/chemotherapy/radiation/targeted therapy/immunotherapy",
                "regimen_or_procedure": "specific regimen name or surgical procedure",
                "cycles_or_fractions": "number of cycles or radiation fractions if applicable",
                "best_response": "CR/PR/SD/PD or surgical outcome (R0/optimal/suboptimal)",
                "toxicities": "notable side effects if mentioned",
                "reason_stopped": "completed/progression/toxicity/patient preference"
            }
        ],

        "recurrence_history": [
            {
                "date": "date of recurrence",
                "site": "location of recurrence",
                "platinum_free_interval_months": "months since last platinum if applicable",
                "platinum_sensitivity": "sensitive/resistant/refractory"
            }
        ],

        "current_disease_status": "NED (no evidence of disease) / stable disease / progressive disease / recurrent / newly diagnosed",
        "current_ecog": "ECOG performance status if mentioned",
        "current_tumor_markers": "most recent CA-125, HE4, or other markers if mentioned",

        "key_comorbidities": ["list of relevant comorbidities that affect treatment decisions"],
        "genetic_syndromes": "Lynch syndrome, BRCA carrier, Li-Fraumeni, etc. or 'none identified'",
        "family_cancer_history": "relevant family history of cancer",

        "summary_for_tumor_board": "2-3 sentence narrative summary suitable for opening a tumor board presentation: who is this patient, what cancer, what has been done, and why are they here now"
    }

    Rules:
    - If a field is not mentioned in any note, use "not reported" or an empty list.
    - Only include information explicitly stated in the notes.
    - Sort treatment_timeline and recurrence_history chronologically by date (oldest → newest).
    - DATES ARE MANDATORY: Every event in treatment_timeline and recurrence_history must have a date_range or date. Every molecular_profile result must include the date it was tested in parentheses, e.g., "BRCA1 pathogenic variant (tested 10/5/25)". Every tumor marker in current_tumor_markers must include its date, e.g., "CA-125 12 U/mL (3/15/26)".
    - For outside patients, clearly distinguish what was done at the outside institution vs. at this institution.
    - Calculate platinum-free interval if the patient had platinum-based chemotherapy and later recurred.
    - The summary_for_tumor_board should be written as if a physician is presenting the case:
      e.g., "This is a 62-year-old G3P3 postmenopausal woman with BRCA1-mutated FIGO IIIC high-grade serous
      ovarian carcinoma, s/p NACT x 3 cycles → R0 interval debulking → adjuvant carboplatin/paclitaxel x 3 cycles,
      now on olaparib maintenance with CA-125 normalized at 12 U/mL. Presented for tumor board review of
      maintenance strategy."
"""


def create_plugin(plugin_config: PluginConfiguration):
    return OncologicHistoryExtractorPlugin(plugin_config)


class OncologicHistoryExtractorPlugin(MedicalReportExtractorBase):
    report_type = "clinical notes"
    system_prompt = ONCOLOGIC_HISTORY_SYSTEM_PROMPT
    error_key = "history"

    # Note types most relevant to oncologic history (lowercase for case-insensitive match)
    # Confirmed in real Rush Caboodle exports: "progress notes", "consults", "ed provider notes"
    # Kept for other Epic configs: "h&p", "discharge summary", "operative report"
    # Added from synthetic data: "procedure note", "procedure notes"
    # Critical for OSH transfer patients (~20-30% of cases):
    #   "unmapped external note" — outside hospital records transferred into Epic
    #   "oncology consultation" — formal GYN oncology consult containing prior history
    #   "addendum note" — molecular/IHC results appended after surgical notes
    #   "genetic counseling" — BRCA/Lynch germline results
    #   "chemotherapy treatment note" — regimen details for treatment_timeline
    _RELEVANT_NOTE_TYPES: frozenset[str] = frozenset(
        t.lower() for t in (
            PROGRESS_NOTE_TYPES + CONSULT_NOTE_TYPES + HP_TYPES + DISCHARGE_TYPES
            + OPERATIVE_TYPES + ED_NOTE_TYPES + ADDENDUM_TYPES
        )
    )
    MAX_NOTES = 30
    MAX_CHARS_PER_NOTE = 4000
    MAX_TOTAL_CHARS = 120_000  # ~30K tokens

    async def _get_clinical_notes(self, patient_id: str) -> list[dict]:
        """Get clinical notes — H&P, consults, referral letters, progress notes.

        Uses get_clinical_notes_by_type when available (avoids JSON roundtrip).
        Falls back to read_all + manual filter for non-Caboodle accessors.
        """
        accessor = self.data_access.clinical_note_accessor

        notes = await accessor.get_clinical_notes_by_type(
            patient_id, list(self._RELEVANT_NOTE_TYPES)
        )

        # Sort by date descending (most recent first) and cap count
        notes.sort(
            key=lambda n: n.get("date", n.get("EntryDate", n.get("OrderDate", ""))),
            reverse=True,
        )
        return notes[:self.MAX_NOTES]

    async def _extract(self, patient_id: str) -> str:
        """Override base to read clinical notes instead of specific report type."""
        notes = await self._get_clinical_notes(patient_id)

        if not notes:
            return json.dumps({
                "patient_id": patient_id,
                "error": "No clinical notes found for this patient.",
                self.error_key: []
            })

        # Build combined text from clinical notes with volume caps
        note_texts = []
        total_chars = 0
        for n in notes:
            text = n.get("text", n.get("NoteText", n.get("note_text", "")))
            if len(text) > self.MAX_CHARS_PER_NOTE:
                text = text[:self.MAX_CHARS_PER_NOTE] + "\n[...truncated...]"
            note_type = n.get("note_type", n.get("NoteType", "Note"))
            date = n.get("date", n.get("EntryDate", n.get("OrderDate", "")))
            entry = f"--- {note_type} ({date}) ---\n{text}"
            if total_chars + len(entry) > self.MAX_TOTAL_CHARS:
                logger.info(
                    "Hit total char cap (%d) for oncologic history, patient %s — using %d of %d notes",
                    self.MAX_TOTAL_CHARS, patient_id, len(note_texts), len(notes),
                )
                break
            note_texts.append(entry)
            total_chars += len(entry)

        combined_text = "\n\n".join(note_texts)

        # LLM extraction
        chat_completion_service: AzureChatCompletion = self.kernel.get_service(service_id="default")
        chat_history = ChatHistory()
        chat_history.add_system_message(textwrap.dedent(self.system_prompt).strip())
        chat_history.add_user_message(
            f"Extract the structured oncologic history from these clinical notes for patient {patient_id}:\n\n{combined_text}"
        )

        settings = AzureChatPromptExecutionSettings(seed=42)
        chat_resp = await chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        )

        response_text = (chat_resp.content or "") if chat_resp is not None else ""

        # Parse JSON from response
        try:
            match = _JSON_FENCE_RE.search(response_text)
            json_str = match.group(1).strip() if match else response_text.strip()
            findings = json.loads(json_str)
            findings["patient_id"] = patient_id
            findings["notes_analyzed"] = len(notes)
            result = json.dumps(findings, indent=2)
        except json.JSONDecodeError:
            result = json.dumps({
                "patient_id": patient_id,
                "notes_analyzed": len(notes),
                "raw_extraction": response_text,
            }, indent=2)

        logger.info("Extracted oncologic history for patient %s from %d notes", patient_id, len(notes))
        return result

    @kernel_function(
        description="Extract structured prior oncologic history from a patient's clinical notes. "
        "Produces a clear timeline of diagnosis, treatments received, recurrences, "
        "current status, and reason for referral. Essential for outside hospital transfers."
    )
    async def extract_oncologic_history(self, patient_id: str) -> str:
        """Extract structured oncologic history from clinical notes.

        Reads all clinical notes (H&P, consultations, referral letters, progress notes)
        and extracts a structured oncologic history including diagnosis date, treatment
        timeline, molecular profile, recurrence history, and reason for referral.

        This is especially valuable for transfer patients from outside hospitals where
        the prior history needs to be clearly organized for the tumor board.

        Args:
            patient_id: The patient ID to retrieve clinical notes for.

        Returns:
            Structured JSON with complete oncologic history timeline.
        """
        if not validate_patient_id(patient_id):
            return json.dumps({"error": "Invalid patient ID."})
        return await self._extract(patient_id)
