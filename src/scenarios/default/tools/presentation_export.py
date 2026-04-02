# Presentation Export Plugin for GYN Oncology Tumor Board
#
# Generates a 5-slide PPTX — one slide per tumor board column:
#   Slide 1 — Patient          (Col 0: case logistics)
#   Slide 2 — Diagnosis        (Col 1: narrative + staging in RED)
#   Slide 3 — Previous Tx      (Col 2: treatment history + CA-125 native chart)
#   Slide 4 — Imaging          (Col 3: dated imaging studies)
#   Slide 5 — Discussion       (Col 4: review types, trial eligibility, plan)
#
# Rendering: PptxGenJS (Node.js) via scripts/tumor_board_slides.js
# Follows the Anthropic PPTX skill (.claude/skills/pptx/SKILL.md)
# Content summarized via Azure ChatCompletion with SlideContent structured output.

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import kernel_function

from data_models.chat_artifact import ChatArtifact, ChatArtifactIdentifier
from data_models.chat_context import ChatContext
from data_models.data_access import DataAccess
from data_models.plugin_configuration import PluginConfiguration
from data_models.tumor_board_summary import SlideContent
from routes.patient_data.patient_data_routes import get_chat_artifacts_url
from utils.model_utils import model_supports_temperature

logger = logging.getLogger(__name__)

OUTPUT_PPTX_FILENAME = "tumor_board_slides-{}.pptx"

# Path to the PptxGenJS script (relative to this file's location in src/)
_SCRIPT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "scripts")
)
_JS_SCRIPT = os.path.join(_SCRIPT_DIR, "tumor_board_slides.js")

SLIDE_SUMMARIZATION_PROMPT = """\
You are preparing a GYN Oncology Tumor Board case presentation.
The primary purpose is to present clinical history so the attending team can discuss the case.
Use clinical shorthand (yo, s/p, dx, bx, LN, mets, etc.) and M/D/YY dates.
Stick to facts from the source data — do not invent or infer.

Slide 1 — Patient logistics (Col 0):
  patient_title: "Case {N} — {LastName}" (use patient_id if name unavailable)
  patient_bullets: max 6 — MRN (ONLY if explicitly in records, else "[MRN - VERIFY]"),
    Attending initials (ONLY if explicitly in records, else "[Attending - VERIFY]"),
    RTC date, Main location, Path date or "NO SLIDES", CA-125 trend only if actively monitored.
    NEVER fabricate an MRN or attending initials.

Slide 2 — Diagnosis & Pertinent History (Col 1):
  diagnosis_title: "Diagnosis & Pertinent History"
  diagnosis_bullets: max 6 — age/sex/cancer dx, key clinical history, reason for
    this tumor board presentation (≤20 words each, facts only)
  primary_site: e.g. "Ovary", "Uterus", "Cervix"
  stage: FIGO stage string, e.g. "IIIC", "IA", "IVB"
  germline_genetics: e.g. "BRCA1+ (c.5266dupC)" or "Negative" or "Not tested"
  somatic_genetics: IHC/molecular one-liner from pathology data

Slide 3 — Previous Tx or Operative Findings (Col 2):
  prevtx_title: "Previous Tx or Operative Findings"
  prevtx_bullets: max 6 — chronological (M/D/YY: event), surgeries, chemo regimens,
    best responses. Facts from the record only.
  findings_chart_title: primary tumor marker name, e.g. "CA-125 Trend"

Slide 4 — Imaging (Col 3):
  imaging_title: "Imaging"
  imaging_bullets: max 8 — one bullet per study: "M/D/YY [Modality]: key findings"
    Chronological, most recent first.

Slide 5 — Discussion agenda (Col 4):
  discussion_title: "Discussion"
  review_types: list the review types needed — ["Path Review", "Imaging Review", "Tx Disc"]
  trial_eligible_note: one-line eligibility summary from the clinical trials data,
    or empty string if no trial data provided
  discussion_bullets: max 6 — open clinical questions and agenda items FOR the
    tumor board to discuss (not recommendations). Drawn from the case facts.
    e.g. "Surgical candidacy given ECOG 2?" or "Platinum sensitivity status?"
  trial_entries: max 3 — only if trial data was provided: "NCT# — Brief title (Phase X)"
    Leave empty list if no trials were identified in the source data.

Respond with valid JSON matching the SlideContent schema exactly.
"""


def create_plugin(plugin_config: PluginConfiguration):
    return PresentationExportPlugin(
        kernel=plugin_config.kernel,
        chat_ctx=plugin_config.chat_ctx,
        data_access=plugin_config.data_access,
    )


class PresentationExportPlugin:
    def __init__(self, kernel, chat_ctx: ChatContext, data_access: DataAccess):
        self.kernel = kernel
        self.chat_ctx = chat_ctx
        self.data_access = data_access

    @kernel_function(
        description="Generate a 5-slide PowerPoint presentation for the GYN tumor board — one slide "
        "per column: Patient, Diagnosis, Previous Tx (with CA-125 chart), Imaging, Discussion."
    )
    async def export_to_pptx(
        self,
        patient_age: str,
        patient_gender: str,
        cancer_type: str,
        pathology_findings: str,
        radiology_findings: str,
        treatment_plan: str,
        clinical_trials: str,
        figo_stage: str = "",
        molecular_profile: str = "",
        tumor_markers: str = "",
        surgical_findings: str = "",
        board_discussion: str = "",
        oncologic_history: str = "",
    ) -> str:
        """Generate a 3-slide PPTX tumor board summary.

        Args:
            patient_age: Patient age.
            patient_gender: Patient gender.
            cancer_type: Cancer type (e.g., "High-grade serous ovarian carcinoma").
            pathology_findings: Pathology findings including IHC and molecular.
            radiology_findings: CT/MRI/PET findings summary.
            treatment_plan: NCCN-based treatment recommendation.
            clinical_trials: Eligible clinical trials summary.
            figo_stage: FIGO stage (e.g., "IIIC").
            molecular_profile: Molecular profile (BRCA, HRD, MMR, etc.).
            tumor_markers: Tumor marker trends (CA-125, HE4, etc.) as JSON or text.
            surgical_findings: Surgical/debulking findings.
            board_discussion: Tumor board consensus discussion points.
            oncologic_history: Structured prior oncologic history (diagnosis, treatments, referral reason).

        Returns:
            str: HTML link to download the generated PPTX file.
        """
        patient_id = self.chat_ctx.patient_id
        conversation_id = self.chat_ctx.conversation_id

        # 1. Summarize all agent data into 5-column SlideContent via LLM
        all_data = {
            "patient_id": patient_id,
            "patient_age": patient_age,
            "patient_gender": patient_gender,
            "cancer_type": cancer_type,
            "figo_stage": figo_stage,
            "molecular_profile": molecular_profile,
            "pathology_findings": pathology_findings,
            "radiology_findings": radiology_findings,
            "tumor_markers": tumor_markers,
            "surgical_findings": surgical_findings,
            "treatment_plan": treatment_plan,
            "clinical_trials": clinical_trials,
            "board_discussion": board_discussion,
            "oncologic_history": oncologic_history,
        }
        slide_content = await self._summarize_for_slides(all_data)

        # 2. Parse raw tumor marker data for native PptxGenJS chart
        markers_raw = self._parse_markers_raw(tumor_markers)

        # 3. Write PPTX via PptxGenJS (scripts/tumor_board_slides.js)
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = tmp.name

        js_input = json.dumps({
            "slides": slide_content.model_dump(),
            "tumor_markers_raw": markers_raw,
            "output_path": tmp_path,
        })

        try:
            proc = await asyncio.create_subprocess_exec(
                "node", _JS_SCRIPT,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(input=js_input.encode())
            if proc.returncode != 0:
                err = stderr.decode()
                logger.error("tumor_board_slides.js failed: %s", err)
                return f"Error generating PPTX: {err[:200]}"

            with open(tmp_path, "rb") as f:
                pptx_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # 4. Upload to blob storage
        artifact_id = ChatArtifactIdentifier(
            conversation_id=conversation_id,
            patient_id=patient_id,
            filename=OUTPUT_PPTX_FILENAME.format(patient_id),
        )
        blob_path = self.data_access.chat_artifact_accessor.get_blob_path(artifact_id)
        output_url = get_chat_artifacts_url(blob_path)

        artifact = ChatArtifact(artifact_id=artifact_id, data=pptx_bytes)
        await self.data_access.chat_artifact_accessor.write(artifact)

        import html as _html
        safe_url = _html.escape(output_url, quote=True)
        safe_name = _html.escape(artifact_id.filename)
        return (
            f"The PowerPoint presentation has been successfully created. "
            f'You can download it using the link below:<br><br>'
            f'<a href="{safe_url}">{safe_name}</a>'
        )

    # ── Helpers ──

    @staticmethod
    def _parse_markers_raw(tumor_markers_str: str) -> list | None:
        """Parse tumor marker JSON string into a list for PptxGenJS chart.
        Returns None if not parseable or fewer than 2 data points.
        """
        if not tumor_markers_str:
            return None
        try:
            data = json.loads(tumor_markers_str)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(data, dict):
            data = data.get("markers", data.get("results", []))
        if not isinstance(data, list) or len(data) < 2:
            return None
        return data

    async def _summarize_for_slides(self, all_data: dict) -> SlideContent:
        """Use LLM to summarize all agent data into SlideContent structure."""
        chat_history = ChatHistory()
        chat_history.add_system_message(SLIDE_SUMMARIZATION_PROMPT)
        chat_history.add_user_message(
            "Agent outputs for slide generation:\n" + json.dumps(all_data, indent=2, default=str)
        )

        if model_supports_temperature():
            settings = AzureChatPromptExecutionSettings(
                temperature=0.0, response_format=SlideContent
            )
        else:
            settings = AzureChatPromptExecutionSettings(response_format=SlideContent)

        chat_service = self.kernel.get_service(service_id="default")
        response = await chat_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        )

        try:
            parsed = json.loads(response.content)
            return SlideContent(**parsed)
        except Exception as exc:
            logger.warning("LLM response did not match SlideContent schema, using fallback: %s", exc)
            pid = all_data.get("patient_id", "Unknown")
            return SlideContent(
                patient_title=f"Case — {pid}",
                patient_bullets=[
                    f"Age: {all_data.get('patient_age', 'N/A')}",
                    f"Cancer: {all_data.get('cancer_type', 'N/A')}",
                ],
                diagnosis_title="Diagnosis & Pertinent History",
                diagnosis_bullets=[
                    f"{all_data.get('patient_age', '?')} yo with {all_data.get('cancer_type', 'unknown cancer')}",
                ],
                primary_site=all_data.get("cancer_type", "Unknown")[:30],
                stage=all_data.get("figo_stage", "Unknown"),
                germline_genetics=all_data.get("molecular_profile", "Not reported")[:80],
                somatic_genetics="See pathology findings",
                prevtx_title="Previous Tx & Operative Findings",
                prevtx_bullets=[all_data.get("oncologic_history", "No history available")[:100]],
                findings_chart_title="Tumor Marker Trend",
                imaging_title="Imaging",
                imaging_bullets=[all_data.get("radiology_findings", "No imaging data")[:100]],
                discussion_title="Discussion",
                review_types=["Tx Disc"],
                trial_eligible_note="",
                discussion_bullets=[
                    all_data.get("treatment_plan", "No treatment plan")[:80],
                    all_data.get("board_discussion", "")[:80],
                ],
                trial_entries=[all_data.get("clinical_trials", "No trials identified")[:80]],
            )
