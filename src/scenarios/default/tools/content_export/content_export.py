# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# Content Export Plugin for GYN Oncology Tumor Board
#
# Generates a landscape 4-column Word document matching the clinical tumor board format:
#   Col 1: Diagnosis & Pertinent History (+ staging in red)
#   Col 2: Previous Tx or Operative Findings, Tumor Markers
#   Col 3: Imaging
#   Col 4: Discussion (action items in red)
#
# One case per page. Clinical shorthand style (s/p, dx, bx, LN, mets, etc.).

from __future__ import annotations

import json
import logging
import os
from io import BytesIO

from azure.core.exceptions import ResourceNotFoundError
from docx.shared import Inches
from docxtpl import DocxTemplate, InlineImage, RichText

# RichText.add() size parameter expects half-points (not Pt objects).
# 9pt = 18, 10pt = 20, 11pt = 22, 12pt = 24
HP_9 = 18   # 9pt in half-points
HP_10 = 20  # 10pt in half-points
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import kernel_function
from semantic_kernel.kernel import Kernel

from data_models.chat_artifact import ChatArtifact, ChatArtifactFilename, ChatArtifactIdentifier
from data_models.chat_context import ChatContext
from data_models.data_access import DataAccess
from data_models.patient_data import PatientTimeline
from data_models.plugin_configuration import PluginConfiguration
from data_models.tumor_board_summary import ClinicalTrial, TumorBoardDocContent
from routes.patient_data.patient_data_routes import get_chat_artifacts_url
from utils.model_utils import model_supports_temperature

OUTPUT_DOC_FILENAME = "tumor_board_review-{}.docx"
TEMPLATE_DOC_FILENAME = "tumor_board_template.docx"

logger = logging.getLogger(__name__)

# Color constants
RED = "cc0000"
TEAL = "007C91"
DARK_TEXT = "333333"
GRAY = "666666"

# Prompt for LLM summarization into 4-column clinical shorthand
TUMOR_BOARD_DOC_PROMPT = """\
You are a GYN oncology tumor board coordinator. Summarize all agent data into
the 4-column tumor board document format using **clinical shorthand**.

Style rules:
- Use standard clinical abbreviations: yo, s/p, dx, bx, LN, mets, c/w, NACT,
  IDS, PDS, BSO, TAH, RATLH, EBRT, VCB, chemo, OSH, neg, pos, w/, bilat, etc.
- Dates as M/D/YY (e.g., 2/20/26 not 2025-02-20)
- Be concise — this is a one-page summary, not a full report
- Cancer history entries start with "-date: event" format
- Action items are short directives (e.g., "Request path on BSO for Rush review.")

Return valid JSON matching the TumorBoardDocContent schema:
{
  "diagnosis_narrative": "Brief patient summary in clinical shorthand. Include age, sex, cancer type, key history, and current reason for presentation. Max 150 words.",
  "primary_site": "e.g., Ovary, Uterus, Cervix",
  "stage": "FIGO stage, e.g., IIIC, IA, IBm-MMRd",
  "germline_genetics": "e.g., BRCA1+ (c.5266dupC), Negative, Not tested",
  "somatic_genetics": "IHC and molecular results one-liner, e.g., MMR retained, ER+ >90%, PR+ >90%, HER2 neg (0), P53 wild type",

  "cancer_history": "Chronological list starting with diagnosis. Each entry: -M/D/YY: Event description. Include procedures, path results, chemo cycles, imaging milestones.",
  "operative_findings": "Most recent operative findings summary. If none, empty string.",
  "pathology_findings": "Most recent pathology summary. Specimen, diagnosis, grade, margins, etc.",
  "tumor_markers": "Marker trend summary, e.g., CA-125: 847→89→24→12 U/mL (normalized)",

  "imaging_findings": "Dated imaging findings. Each study: Modality M/D/YY OSH/Rush\\nFindings. Include impression.",

  "discussion": "Tumor board discussion points: path review needs, treatment discussion, trial eligibility, plan.",
  "action_items": ["Short action directives shown in red, e.g., Request path on BSO for Rush review.", "Begin Megace & repeat biopsy in 3 months."]
}
"""


def create_plugin(plugin_config: PluginConfiguration):
    return ContentExportPlugin(
        kernel=plugin_config.kernel,
        chat_ctx=plugin_config.chat_ctx,
        data_access=plugin_config.data_access,
    )


class ContentExportPlugin:
    def __init__(self, kernel: Kernel, chat_ctx: ChatContext, data_access: DataAccess):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.chat_ctx = chat_ctx
        self.data_access = data_access
        self.kernel = kernel

    @kernel_function(
        description="Generate a landscape 4-column Word document for the GYN tumor board. "
        "Produces the standard tumor board one-page summary: Diagnosis & History, "
        "Previous Tx/Operative Findings, Imaging, and Discussion."
    )
    async def export_to_word_doc(
        self,
        patient_gender: str,
        patient_age: str,
        medical_history: str,
        social_history: str,
        cancer_type: str,
        ct_scan_findings: list[str],
        x_ray_findings: list[str],
        pathology_findings: list[str],
        treatment_plan: str,
        clinical_trials: list[ClinicalTrial],
        figo_stage: str = "",
        molecular_profile: str = "",
        tumor_markers: str = "",
        surgical_findings: str = "",
        board_discussion: str = "",
        oncologic_history: str = "",
    ) -> str:
        """Generate a landscape 4-column Word document for GYN Tumor Board review.

        Matches the standard tumor board format: one case per page with columns for
        Diagnosis & Pertinent History, Previous Tx/Operative Findings/Tumor Markers,
        Imaging, and Discussion.

        Args:
            patient_gender: Patient gender.
            patient_age: Patient age.
            medical_history: Summarized medical history.
            social_history: Summarized social history.
            cancer_type: Cancer type (e.g., "High-grade serous ovarian carcinoma").
            ct_scan_findings: CT/MRI/PET-CT findings.
            x_ray_findings: Additional imaging findings.
            pathology_findings: Pathology findings including IHC and molecular.
            treatment_plan: Treatment recommendation.
            clinical_trials: Eligible clinical trials.
            figo_stage: FIGO stage (e.g., "IIIC").
            molecular_profile: Molecular profile summary.
            tumor_markers: Tumor marker trends.
            surgical_findings: Surgical/debulking findings.
            board_discussion: Tumor board consensus discussion points.
            oncologic_history: Structured prior oncologic history.

        Returns:
            str: HTML link to download the generated Word file.
        """
        conversation_id = self.chat_ctx.conversation_id
        patient_id = self.chat_ctx.patient_id

        # 1. Collect all agent data
        all_data = {
            "patient_id": patient_id,
            "patient_age": patient_age,
            "patient_gender": patient_gender,
            "medical_history": medical_history,
            "social_history": social_history,
            "cancer_type": cancer_type,
            "figo_stage": figo_stage,
            "molecular_profile": molecular_profile,
            "pathology_findings": pathology_findings,
            "ct_scan_findings": ct_scan_findings,
            "x_ray_findings": x_ray_findings,
            "tumor_markers": tumor_markers,
            "surgical_findings": surgical_findings,
            "treatment_plan": treatment_plan,
            "clinical_trials": [
                {"title": t.title, "summary": t.summary, "url": t.url}
                for t in clinical_trials
            ] if clinical_trials else [],
            "board_discussion": board_discussion,
            "oncologic_history": oncologic_history,
        }
        logger.info(f"Generating tumor board doc for patient {patient_id}")

        # 2. Summarize into 4-column clinical shorthand via LLM
        doc_content = await self._summarize_for_tumor_board_doc(all_data)

        # 3. Load template and render with RichText
        doc_template_path = os.path.join(self.root_dir, "templates", TEMPLATE_DOC_FILENAME)
        if not os.path.exists(doc_template_path):
            logger.error(f"Template not found: {doc_template_path}")
            return f"Error: Word template not found at {doc_template_path}"
        doc = DocxTemplate(doc_template_path)

        doc_data = {
            "col1_content": self._build_col1_richtext(doc, doc_content),
            "col2_content": self._build_col2_richtext(doc, doc_content),
            "col3_content": self._build_col3_richtext(doc, doc_content),
            "col4_content": self._build_col4_richtext(doc, doc_content),
        }

        doc.render(doc_data)

        # 4. Save to blob storage
        artifact_id = ChatArtifactIdentifier(
            conversation_id=conversation_id,
            patient_id=patient_id,
            filename=OUTPUT_DOC_FILENAME.format(patient_id),
        )
        doc_blob_path = self.data_access.chat_artifact_accessor.get_blob_path(artifact_id)
        doc_output_url = get_chat_artifacts_url(doc_blob_path)

        stream = BytesIO()
        doc.save(stream)
        stream.seek(0)

        artifact = ChatArtifact(artifact_id=artifact_id, data=stream.getvalue())
        await self.data_access.chat_artifact_accessor.write(artifact)

        return (
            f"The tumor board Word document has been created. "
            f'Download: <a href="{doc_output_url}">{artifact_id.filename}</a>'
        )

    # ── Column RichText builders ──

    @staticmethod
    def _build_col1_richtext(doc, c: TumorBoardDocContent) -> RichText:
        """Column 1: Diagnosis & Pertinent History."""
        rt = RichText()

        # Main narrative
        rt.add(c.diagnosis_narrative, font="Calibri", size=HP_9, color=DARK_TEXT)

        # Staging section (in teal, at bottom)
        rt.add("\n\n", font="Calibri", size=HP_9)
        rt.add(f"Primary Site: {c.primary_site}\n", font="Calibri", size=HP_9, color=TEAL, bold=True)
        rt.add(f"Stage: {c.stage}\n", font="Calibri", size=HP_9, color=TEAL, bold=True)
        rt.add(f"Germline genetics:  {c.germline_genetics}\n", font="Calibri", size=HP_9, color=TEAL, bold=True)
        rt.add(f"Somatic genetics: {c.somatic_genetics}", font="Calibri", size=HP_9, color=TEAL, bold=True)

        return rt

    @staticmethod
    def _build_col2_richtext(doc, c: TumorBoardDocContent) -> RichText:
        """Column 2: Previous Tx or Operative Findings, Tumor Markers."""
        rt = RichText()

        # Cancer history (chronological)
        if c.cancer_history:
            rt.add("Cancer History\n", font="Calibri", size=HP_9, bold=True, underline=True, color=DARK_TEXT)
            rt.add(c.cancer_history, font="Calibri", size=HP_9, color=DARK_TEXT)

        # Operative findings
        if c.operative_findings:
            rt.add("\n\n", font="Calibri", size=HP_9)
            rt.add("Operative Findings\n", font="Calibri", size=HP_9, bold=True, underline=True, color=DARK_TEXT)
            rt.add(c.operative_findings, font="Calibri", size=HP_9, color=DARK_TEXT)

        # Pathology
        if c.pathology_findings:
            rt.add("\n\n", font="Calibri", size=HP_9)
            rt.add("Path\n", font="Calibri", size=HP_9, bold=True, underline=True, color=DARK_TEXT)
            rt.add(c.pathology_findings, font="Calibri", size=HP_9, color=DARK_TEXT)

        # Tumor markers
        if c.tumor_markers:
            rt.add("\n\n", font="Calibri", size=HP_9)
            rt.add("Tumor Markers\n", font="Calibri", size=HP_9, bold=True, underline=True, color=DARK_TEXT)
            rt.add(c.tumor_markers, font="Calibri", size=HP_9, color=DARK_TEXT)

        return rt

    @staticmethod
    def _build_col3_richtext(doc, c: TumorBoardDocContent) -> RichText:
        """Column 3: Imaging."""
        rt = RichText()
        rt.add(c.imaging_findings, font="Calibri", size=HP_9, color=DARK_TEXT)
        return rt

    @staticmethod
    def _build_col4_richtext(doc, c: TumorBoardDocContent) -> RichText:
        """Column 4: Discussion."""
        rt = RichText()

        # Main discussion text
        rt.add(c.discussion, font="Calibri", size=HP_9, bold=True, color=DARK_TEXT)

        # Action items in red
        if c.action_items:
            rt.add("\n\n", font="Calibri", size=HP_9)
            for item in c.action_items:
                rt.add(f"{item}\n", font="Calibri", size=HP_9, color=RED, bold=True)

        return rt

    # ── LLM Summarization ──

    async def _summarize_for_tumor_board_doc(self, all_data: dict) -> TumorBoardDocContent:
        """Summarize all agent data into 4-column tumor board format via LLM."""
        chat_history = ChatHistory()
        chat_history.add_system_message(TUMOR_BOARD_DOC_PROMPT)
        chat_history.add_user_message(
            "Agent outputs for tumor board document:\n" + json.dumps(all_data, indent=2, default=str)
        )

        if model_supports_temperature():
            settings = AzureChatPromptExecutionSettings(
                temperature=0.0, response_format=TumorBoardDocContent
            )
        else:
            settings = AzureChatPromptExecutionSettings(response_format=TumorBoardDocContent)

        chat_service = self.kernel.get_service(service_id="default")
        response = await chat_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        )

        try:
            parsed = json.loads(response.content)
            return TumorBoardDocContent(**parsed)
        except Exception:
            logger.warning("LLM response did not match TumorBoardDocContent schema, using fallback")
            return self._fallback_doc_content(all_data)

    @staticmethod
    def _fallback_doc_content(data: dict) -> TumorBoardDocContent:
        """Fallback if LLM summarization fails — use raw data truncated."""
        return TumorBoardDocContent(
            diagnosis_narrative=(
                f"{data.get('patient_age', '?')} yo {data.get('patient_gender', '')} "
                f"with {data.get('cancer_type', 'unknown cancer')}. "
                f"{str(data.get('medical_history', ''))[:200]}"
            ),
            primary_site=data.get("cancer_type", "Unknown")[:30],
            stage=data.get("figo_stage", "Unknown"),
            germline_genetics=data.get("molecular_profile", "Not reported")[:100],
            somatic_genetics="See pathology findings",
            cancer_history=str(data.get("oncologic_history", ""))[:500],
            operative_findings=str(data.get("surgical_findings", ""))[:300],
            pathology_findings="\n".join(
                str(f)[:100] for f in data.get("pathology_findings", [])
            )[:400],
            tumor_markers=str(data.get("tumor_markers", ""))[:200],
            imaging_findings="\n".join(
                str(f)[:100] for f in data.get("ct_scan_findings", [])
            )[:400],
            discussion=(
                f"Tx Plan: {str(data.get('treatment_plan', ''))[:200]}\n\n"
                f"{str(data.get('board_discussion', ''))[:200]}"
            ),
            action_items=[],
        )

    # ── Legacy helpers (kept for backward compatibility) ──

    async def _get_patient_images(
        self, doc: DocxTemplate, image_types: set[str], image_height: float = 1.7
    ) -> list[InlineImage]:
        patient_id = self.chat_ctx.patient_id
        inline_images = []

        for img in self.chat_ctx.patient_data:
            if img["type"] in image_types:
                img_stream = await self.data_access.image_accessor.read(patient_id, img["filename"])
                inline_images.append(InlineImage(doc, img_stream, height=Inches(image_height)))
        for img in self.chat_ctx.output_data:
            if img["type"] in image_types:
                artifact_id = ChatArtifactIdentifier(
                    self.chat_ctx.conversation_id, patient_id, filename=img["filename"]
                )
                artifact = await self.data_access.chat_artifact_accessor.read(artifact_id)
                inline_images.append(InlineImage(doc, BytesIO(artifact.data), height=Inches(image_height)))

        return inline_images

    async def _load_patient_timeline(self) -> PatientTimeline:
        artifact_id = ChatArtifactIdentifier(
            conversation_id=self.chat_ctx.conversation_id,
            patient_id=self.chat_ctx.patient_id,
            filename=ChatArtifactFilename.PATIENT_TIMELINE,
        )
        artifact = await self.data_access.chat_artifact_accessor.read(artifact_id)
        return PatientTimeline.model_validate_json(artifact.data.decode("utf-8"))

    async def _load_research_papers(self) -> dict:
        artifact_id = ChatArtifactIdentifier(
            conversation_id=self.chat_ctx.conversation_id,
            patient_id=self.chat_ctx.patient_id,
            filename=ChatArtifactFilename.RESEARCH_PAPERS,
        )
        try:
            artifact = await self.data_access.chat_artifact_accessor.read(artifact_id)
            return json.loads(artifact.data.decode("utf-8"))
        except ResourceNotFoundError:
            return {}

    @staticmethod
    def _get_clinical_trials(doc: DocxTemplate, clinical_trials: list[ClinicalTrial]) -> list[dict]:
        return [
            {
                "title": RichText(
                    trial.title, color="0000ee", underline=True,
                    url_id=doc.build_url_id(trial.url),
                ),
                "summary": trial.summary,
            }
            for trial in clinical_trials
        ]
