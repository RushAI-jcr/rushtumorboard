# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class ClinicalSummary:
    entries: list[str]


@dataclass(frozen=True)
class ClinicalTrial:
    title: str
    summary: str
    url: str


class TumorBoardDocContent(BaseModel):
    """Structured output for the 4-column landscape tumor board Word document.
    LLM fills this from all agent outputs in clinical shorthand style.
    Must be Pydantic BaseModel for Azure OpenAI response_format."""

    # Column 1: Diagnosis & Pertinent History
    diagnosis_narrative: str       # e.g. "66 yo with new Sertoli-Leydig cell tumor of the ovary..."
    primary_site: str              # e.g. "Ovary"
    stage: str                     # e.g. "IA"
    germline_genetics: str         # e.g. "BRCA1 pathogenic variant (c.5266dupC)"
    somatic_genetics: str          # e.g. "MMR retained, ER+ >90%, PR+ >90%, HER2 neg, P53 wild type"

    # Column 2: Previous Tx or Operative Findings, Tumor Markers
    cancer_history: str            # Chronological: "-date: event\n-date: event"
    operative_findings: str        # Most recent operative note summary
    pathology_findings: str        # Most recent path summary
    tumor_markers: str             # e.g. "CA-125: 847→89→24→12 U/mL (normalized)"

    # Column 3: Imaging
    imaging_findings: str          # Dated imaging findings

    # Column 4: Discussion
    discussion: str                # Path review, Tx Disc, trial eligibility, plan
    action_items: list[str]        # Items needing action (shown in red)


class SlideContent(BaseModel):
    """Structured output for 3-slide PPTX generation.
    LLM fills this from all agent outputs; schema enforces slide-friendly limits.
    Must be Pydantic BaseModel for Azure OpenAI response_format."""
    overview_title: str          # e.g. "Patient GYN-001 — HGSC Ovarian"
    overview_subtitle: str       # e.g. "FIGO IIIC | BRCA1+ | 2026-03-12"
    overview_bullets: list[str]  # max 6, ≤20 words each
    findings_title: str          # e.g. "Pathology & Imaging Findings"
    findings_bullets: list[str]  # max 6
    findings_chart_title: str    # e.g. "CA-125 Trend"
    treatment_title: str         # e.g. "Treatment Plan & Clinical Trials"
    treatment_bullets: list[str] # max 6
    trial_entries: list[str]     # max 3, formatted "NCT# — Title"
