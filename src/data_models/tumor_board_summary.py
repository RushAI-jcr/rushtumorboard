# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from dataclasses import dataclass


@dataclass(frozen=True)
class ClinicalSummary:
    entries: list[str]


@dataclass(frozen=True)
class ClinicalTrial:
    title: str
    summary: str
    url: str


@dataclass
class SlideContent:
    """Structured output for 3-slide PPTX generation.
    LLM fills this from all agent outputs; schema enforces slide-friendly limits."""
    overview_title: str          # e.g. "Patient GYN-001 — HGSC Ovarian"
    overview_subtitle: str       # e.g. "FIGO IIIC | BRCA1+ | 2026-03-12"
    overview_bullets: list[str]  # max 6, ≤20 words each
    findings_title: str          # e.g. "Pathology & Imaging Findings"
    findings_bullets: list[str]  # max 6
    findings_chart_title: str    # e.g. "CA-125 Trend"
    treatment_title: str         # e.g. "Treatment Plan & Clinical Trials"
    treatment_bullets: list[str] # max 6
    trial_entries: list[str]     # max 3, formatted "NCT# — Title"
