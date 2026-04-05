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
    """Structured output for the 5-column landscape tumor board Word document.
    LLM fills this from all agent outputs in clinical shorthand style.
    Must be Pydantic BaseModel for Azure OpenAI response_format."""

    # Column 0: Patient metadata (matches real tumor board handout format)
    case_number: int = 1           # Sequential case number for the meeting — no automated data source; set by the LLM based on order presented
    patient_last_name: str = ""    # Last name only (display on handout)
    mrn: str = "[MRN - VERIFY]"    # MRN number — no grounded data source; placeholder for clinician
    attending_initials: str = "[Attending - VERIFY]"  # Attending initials — no grounded data source
    is_inpatient: bool = False     # Adds "Inpt" flag if True
    rtc: str = "None"              # Return to clinic: "3/10 AL", "Inpt, 3/11 SO", "None"
    main_location: str = ""        # e.g. "RAB", "BG", "Copley"
    path_date: str = "NO SLIDES"   # Path slide date: "20-Feb", "10/23/2025", or "NO SLIDES"
    ca125_trend_in_col0: str = ""  # CA-125 trend when clinically notable (active trending)

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

    # Column 3: Imaging (MOST RECENT FIRST)
    imaging_findings: str          # "Modality Date" header + impression block, reverse chronological

    # Column 4: Discussion
    review_types: list[str] = ["Tx Disc"]   # e.g. ["Path Review", "Imaging Review", "Tx Disc"]
    trial_eligible_note: str = ""           # Free text after "Eligible for trial?" prompt
    discussion: str                          # ALL discussion text rendered in RED — plan/consensus
    action_items: list[str] = []              # Additional directives embedded with discussion (also RED)


class SlideContent(BaseModel):
    """Structured output for 5-slide PPTX generation — one slide per tumor board column.
    LLM fills this from all agent outputs in dense clinical shorthand matching the
    Rush GYN tumor board handout style. Must be Pydantic BaseModel for Azure OpenAI response_format."""

    # Slide 1: Patient (Col 0) — metadata / logistics
    patient_title: str            # e.g. "Case 1 — L Pyfer"
    patient_bullets: list[str]    # max 6: MRN, Attending initials, Inpt, RTC, Location, Path date, CA-125 trend

    # Slide 2: Diagnosis & Pertinent History (Col 1)
    diagnosis_title: str          # e.g. "Diagnosis & Pertinent History"
    diagnosis_bullets: list[str]  # max 6: dense clinical shorthand — age/cancer/hx/presentation
    primary_site: str             # shown in red — "Ovary", "Uterus", "Cervix", etc.
    stage: str                    # shown in red — FIGO stage
    germline_genetics: str        # shown in red — one-liner
    somatic_genetics: str         # shown in red — ALL IHC + NGS on one line

    # Slide 3: Previous Tx or Operative Findings, Tumor Markers (Col 2)
    prevtx_title: str             # e.g. "Previous Tx & Operative Findings"
    prevtx_bullets: list[str]     # max 6: op findings, path, cancer hx, tumor markers — chronological
    findings_chart_title: str     # e.g. "CA-125 Trend"

    # Slide 4: Imaging (Col 3) — MOST RECENT FIRST
    imaging_title: str            # e.g. "Imaging"
    imaging_bullets: list[str]    # max 8: "Modality Date [OSH]" header + impression, reverse chronological

    # Slide 5: Discussion (Col 4)
    discussion_title: str         # e.g. "Discussion"
    review_types: list[str]       # e.g. ["Path Review", "Tx Disc"]
    trial_eligible_note: str      # brief WITHOUT parens: "Surveillance", "Eligible for CLEO trial", or ""
    discussion_bullets: list[str]  # max 4: ultra-concise plan/consensus, action items embedded (ALL RED)
    trial_entries: list[str]      # max 3: "NCT# — Brief title (Phase X)" from ClinicalTrials
    references: list[str] = []    # max 4: PubMed citations "PMID:XXXXXXXX — Author et al. Journal YYYY"
