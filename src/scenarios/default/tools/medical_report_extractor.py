# Shared base class for LLM-based medical report extraction (pathology, radiology).
#
# Implements a 3-layer fallback strategy:
#   Layer 1: Dedicated report CSV (pathology_reports.csv / radiology_reports.csv)
#   Layer 2: Domain-specific clinical note types (Operative Report, Procedures, etc.)
#   Layer 3: General notes (Progress Notes, H&P, Consults) filtered by keywords
#
# Subclasses provide: report_type, accessor_method, system_prompt, error_key,
# and the layer2/layer3 note types and keywords.

import json
import logging
import re
import textwrap

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory

from data_models.plugin_configuration import PluginConfiguration

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _report_date_key(r: dict) -> str:
    """Sort key for clinical reports: OrderDate → EntryDate → date → order_date."""
    return r.get("OrderDate", r.get("EntryDate", r.get("date", r.get("order_date", ""))))


class MedicalReportExtractorBase:
    """Base class for LLM-based medical report extraction plugins.

    Uses a 3-layer fallback to find the best available data:
      Layer 1: Dedicated report CSV (e.g., pathology_reports.csv)
      Layer 2: Domain-specific NoteTypes from clinical_notes.csv
      Layer 3: General clinical notes filtered by domain keywords
    """

    # Subclasses must override these
    report_type: str = ""              # e.g. "pathology", "radiology"
    accessor_method: str = ""          # e.g. "get_pathology_reports"
    system_prompt: str = ""            # Full LLM system prompt
    error_key: str = "findings"        # Key name in empty error response

    # Layered fallback configuration — subclasses override (tuples to prevent mutation)
    layer2_note_types: tuple[str, ...] = ()
    layer3_note_types: tuple[str, ...] = ()
    layer3_keywords: tuple[str, ...] = ()

    # Volume caps to prevent LLM context window overflow
    MAX_REPORTS = 25
    MAX_CHARS_PER_REPORT = 4000
    MAX_TOTAL_CHARS = 80_000  # ~20K tokens, leaves room for system prompt

    # Human-readable descriptions of the 3 fallback layers (keyed by source_layer int)
    _LAYER_DESCRIPTIONS: dict[int, str] = {
        1: "Dedicated report CSV",
        2: "Domain-specific clinical notes (operative/procedure notes)",
        3: "Keyword-matched general clinical notes (progress notes, H&P, consults)",
    }

    def __init__(self, config: PluginConfiguration):
        self.kernel = config.kernel
        self.chat_ctx = config.chat_ctx
        self.data_access = config.data_access

    async def _extract(self, patient_id: str) -> str:
        """Layered extraction: dedicated reports → domain notes → keyword-filtered notes → LLM."""
        accessor = self.data_access.clinical_note_accessor

        # --- Layer 1: Dedicated report CSV ---
        reports = []
        source_layer = 1
        if hasattr(accessor, self.accessor_method):
            reports = await getattr(accessor, self.accessor_method)(patient_id)

        # --- Layer 2: Domain-specific NoteTypes ---
        if not reports and self.layer2_note_types:
            reports = await accessor.get_clinical_notes_by_type(patient_id, self.layer2_note_types)
            if reports:
                source_layer = 2
                logger.info(
                    "Layer 2 fallback: found %d %s-relevant notes (types: %s) for patient %s",
                    len(reports), self.report_type, self.layer2_note_types, patient_id,
                )

        # --- Layer 3: General notes with keyword filtering ---
        if not reports and self.layer3_note_types and self.layer3_keywords:
            reports = await accessor.get_clinical_notes_by_keywords(
                patient_id, self.layer3_note_types, self.layer3_keywords
            )
            if reports:
                source_layer = 3
                logger.info(
                    "Layer 3 fallback: found %d keyword-matched notes for %s, patient %s",
                    len(reports), self.report_type, patient_id,
                )

        if not reports:
            return json.dumps({
                "patient_id": patient_id,
                "error": f"No {self.report_type} reports found for this patient across all data layers.",
                self.error_key: []
            })

        # Sort chronologically (oldest → newest) so the LLM sees progression over time.
        # Use OrderDate for dedicated reports, EntryDate for clinical notes.
        reports = sorted(reports, key=_report_date_key)

        # Cap report count to prevent context window overflow.
        # Keep the NEWEST reports (most clinically relevant for tumor board).
        total_available = len(reports)
        if total_available > self.MAX_REPORTS:
            oldest_dropped = _report_date_key(reports[0])
            newest_kept = _report_date_key(reports[-self.MAX_REPORTS])
            logger.info(
                "Capping %s reports from %d to %d for patient %s (layer %d) — keeping most recent (from %s onward); dropped %d older reports before %s",
                self.report_type, total_available, self.MAX_REPORTS, patient_id, source_layer,
                newest_kept, total_available - self.MAX_REPORTS, oldest_dropped,
            )
            reports = reports[-self.MAX_REPORTS:]

        # Build combined report text with source context and volume caps
        report_texts = []
        total_chars = 0
        for r in reports:
            text = r.get("ReportText", r.get("report_text", r.get("NoteText", r.get("note_text", r.get("text", "")))))
            if len(text) > self.MAX_CHARS_PER_REPORT:
                text = text[:self.MAX_CHARS_PER_REPORT] + "\n[...truncated...]"
            proc = r.get("ProcedureName", r.get("procedure_name", r.get("NoteType", r.get("note_type", ""))))
            date = r.get("OrderDate", r.get("EntryDate", r.get("date", "")))
            label = "Report" if source_layer == 1 else "Clinical Note"
            entry = f"--- {label}: {proc} ({date}) ---\n{text}"
            if total_chars + len(entry) > self.MAX_TOTAL_CHARS:
                logger.info(
                    "Hit total char cap (%d) for %s extraction, patient %s — using %d of %d reports",
                    self.MAX_TOTAL_CHARS, self.report_type, patient_id, len(report_texts), len(reports),
                )
                break
            report_texts.append(entry)
            total_chars += len(entry)

        combined_text = "\n\n".join(report_texts)

        # Build user message with layer context
        if source_layer == 1:
            user_preamble = f"Extract structured {self.report_type} findings from these dedicated {self.report_type} reports:"
        elif source_layer == 2:
            user_preamble = (
                f"No dedicated {self.report_type} reports are available for this patient. "
                f"Extract any {self.report_type} findings from these procedure/operative notes "
                f"that may contain {self.report_type} information:"
            )
        else:
            user_preamble = (
                f"No dedicated {self.report_type} reports are available for this patient. "
                f"Extract any {self.report_type} information from these clinical notes where "
                f"the physician may have summarized or referenced {self.report_type} findings:"
            )

        # LLM extraction
        chat_completion_service: AzureChatCompletion = self.kernel.get_service(service_id="default")
        chat_history = ChatHistory()
        chat_history.add_system_message(textwrap.dedent(self.system_prompt).strip())
        chat_history.add_user_message(f"{user_preamble}\n\n{combined_text}")

        settings = AzureChatPromptExecutionSettings(seed=42)
        chat_resp = await chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        )

        response_text = (chat_resp.content or "") if chat_resp is not None else ""
        if not response_text:
            logger.warning("Empty LLM response for %s extraction, patient %s", self.report_type, patient_id)
            return json.dumps({
                "patient_id": patient_id,
                "error": f"LLM returned empty response for {self.report_type} extraction.",
                self.error_key: []
            })

        # Parse JSON from response
        try:
            match = _JSON_FENCE_RE.search(response_text)
            json_str = match.group(1).strip() if match else response_text.strip()
            findings = json.loads(json_str)
            findings["patient_id"] = patient_id
            findings["report_count"] = len(reports)
            findings["data_source_layer"] = source_layer
            findings["data_source_description"] = self._LAYER_DESCRIPTIONS[source_layer]
            if total_available > self.MAX_REPORTS:
                findings["truncation_note"] = (
                    f"{total_available} {self.report_type} sources available; "
                    f"{self.MAX_REPORTS} sent to LLM due to context limits."
                )
            result = json.dumps(findings, indent=2)
        except json.JSONDecodeError:
            result = json.dumps({
                "patient_id": patient_id,
                "report_count": len(reports),
                "data_source_layer": source_layer,
                "raw_extraction": response_text,
            }, indent=2)

        logger.info(
            "Extracted %s findings for patient %s (layer %d, %d sources)",
            self.report_type, patient_id, source_layer, len(reports),
        )
        return result
