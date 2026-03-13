# Shared base class for LLM-based medical report extraction (pathology, radiology).
#
# Eliminates code duplication between pathology_extractor.py and radiology_extractor.py.
# Subclasses only need to provide: report_type, accessor_method, fallback_note_type,
# system_prompt, and error_key.

import json
import logging
import textwrap

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory

from data_models.plugin_configuration import PluginConfiguration

logger = logging.getLogger(__name__)


class MedicalReportExtractorBase:
    """Base class for LLM-based medical report extraction plugins."""

    # Subclasses must override these
    report_type: str = ""              # e.g. "pathology", "radiology"
    accessor_method: str = ""          # e.g. "get_pathology_reports"
    fallback_note_type: str = ""       # e.g. "pathology", "radiology"
    system_prompt: str = ""            # Full LLM system prompt
    error_key: str = "findings"        # Key name in empty error response

    def __init__(self, config: PluginConfiguration):
        self.kernel = config.kernel
        self.chat_ctx = config.chat_ctx
        self.data_access = config.data_access

    async def _extract(self, patient_id: str) -> str:
        """Shared extraction logic: fetch reports → LLM → parse JSON."""
        # Get reports from data accessor
        accessor = self.data_access.clinical_note_accessor
        if hasattr(accessor, self.accessor_method):
            reports = await getattr(accessor, self.accessor_method)(patient_id)
        else:
            all_notes = await accessor.read_all(patient_id)
            reports = []
            for note_json in all_notes:
                note = json.loads(note_json) if isinstance(note_json, str) else note_json
                if self.fallback_note_type in note.get("note_type", "").lower():
                    reports.append(note)

        if not reports:
            return json.dumps({
                "patient_id": patient_id,
                "error": f"No {self.report_type} reports found for this patient.",
                self.error_key: []
            })

        # Build combined report text
        report_texts = []
        for r in reports:
            text = r.get("ReportText", r.get("report_text", r.get("text", "")))
            proc = r.get("ProcedureName", r.get("procedure_name", ""))
            date = r.get("OrderDate", r.get("date", ""))
            label = "Report" if self.report_type == "pathology" else "Study"
            report_texts.append(f"--- {label}: {proc} ({date}) ---\n{text}")

        combined_text = "\n\n".join(report_texts)

        # LLM extraction
        chat_completion_service: AzureChatCompletion = self.kernel.get_service(service_id="default")
        chat_history = ChatHistory()
        chat_history.add_system_message(textwrap.dedent(self.system_prompt).strip())
        chat_history.add_user_message(
            f"Extract structured {self.report_type} findings from these reports:\n\n{combined_text}"
        )

        settings = AzureChatPromptExecutionSettings(seed=42)
        chat_resp = await chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        )

        response_text = chat_resp.content

        # Parse JSON from response
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text

            findings = json.loads(json_str)
            findings["patient_id"] = patient_id
            findings["report_count"] = len(reports)
            result = json.dumps(findings, indent=2)
        except (json.JSONDecodeError, IndexError):
            result = json.dumps({
                "patient_id": patient_id,
                "report_count": len(reports),
                "raw_extraction": response_text,
            }, indent=2)

        logger.info(f"Extracted {self.report_type} findings for patient {patient_id}")
        return result
