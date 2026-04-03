---
name: pptx-export
description: Generate GYN tumor board 5-slide PowerPoint presentations using PptxGenJS (Anthropic PPTX skill)
---

# PPTX Export for GYN Tumor Board

Generates a 5-slide `.pptx` per patient using **PptxGenJS** (Node.js) via
`scripts/tumor_board_slides.js`. One slide per tumor board column.
Follows the Anthropic PPTX skill at `.claude/skills/pptx/SKILL.md`.

## 5-Slide Layout (one per tumor board column)

| Slide | Column | Content |
|-------|--------|---------|
| 1 | Col 0 — Patient | Case number, MRN, attending, RTC, location, path date, CA-125 if notable |
| 2 | Col 1 — Diagnosis | Narrative bullets + staging block in **RED** (Primary Site, Stage, Germline, Somatic) |
| 3 | Col 2 — Previous Tx | Treatment history bullets + native PptxGenJS CA-125 line chart |
| 4 | Col 3 — Imaging | Dated imaging studies (two-column for long lists) |
| 5 | Col 4 — Discussion | Review types header → "Eligible for trial?" → plan bullets → trials |

## Workflow

1. LLM summarizes agent outputs into `SlideContent` (response_format=SlideContent, temp=0)
2. `presentation_export.py` pipes `SlideContent` JSON + raw marker data to `scripts/tumor_board_slides.js` via stdin
3. Node.js script generates the PPTX using PptxGenJS and writes to a temp file
4. Python reads the temp file and uploads to Azure Blob Storage

## Key Files

- Plugin: `src/scenarios/default/tools/presentation_export.py`
- JS script: `scripts/tumor_board_slides.js`
- Node deps: `scripts/package.json` (`pptxgenjs ^3.12.0`)
- Schema: `src/data_models/tumor_board_summary.py` (`SlideContent`)
- Anthropic skill: `.claude/skills/pptx/SKILL.md` + `pptxgenjs.md`

## Setup

```sh
cd scripts && npm install
```

## Design Rules (from Anthropic PPTX skill)

- Navy `1B365D` header bar on every slide; teal `007C91` accents
- Calibri font throughout (matches Word doc)
- RED `FF0000` for staging/genetics on slide 2 (matches real tumor board REDTEXT)
- Native PptxGenJS LINE chart for CA-125 (no matplotlib PNG)
- No accent underlines under titles
- Slide badge `N / 5` in top-right corner
- NEVER use `#` prefix on hex colors (corrupts file)
- NEVER reuse option objects across addShape calls

## Testing

```sh
echo '{
  "slides": {
    "patient_title": "Case 1 — Test",
    "patient_bullets": ["MRN: 1234567", "Attending: SD", "RTC: 3/10 SD", "RAB", "Path: 20-Feb"],
    "diagnosis_title": "Diagnosis & Pertinent History",
    "diagnosis_bullets": ["62 yo with recurrent HGSC ovarian cancer"],
    "primary_site": "Ovary", "stage": "IIIC Recurrent",
    "germline_genetics": "BRCA2 somatic", "somatic_genetics": "HRD positive",
    "prevtx_title": "Previous Tx & Operative Findings",
    "prevtx_bullets": ["2/20/26: RATLH/BSO — benign findings"],
    "findings_chart_title": "CA-125 Trend",
    "imaging_title": "Imaging",
    "imaging_bullets": ["2/23/26 CT CAP: No evidence of metastatic disease"],
    "discussion_title": "Discussion",
    "review_types": ["Imaging Review", "Tx Disc"],
    "trial_eligible_note": "",
    "discussion_bullets": ["Agree with plan to stop Lynparza if Signatera negative"],
    "trial_entries": []
  },
  "tumor_markers_raw": null,
  "output_path": "/tmp/test_tb.pptx"
}' | node scripts/tumor_board_slides.js
```
