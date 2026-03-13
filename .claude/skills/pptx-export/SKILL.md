---
name: pptx-export
description: Use this skill when generating GYN tumor board PowerPoint presentations. Covers python-pptx slide building, chart embedding, 3-slide layout, and structured output summarization.
---

# PPTX Export for GYN Tumor Board

## Overview
Generates a 3-slide `.pptx` presentation per patient using `python-pptx`.
Template is generated programmatically via `scripts/generate_pptx_template.py`.

## 3-Slide Structure

| Slide | Layout | Content Sources |
|-------|--------|----------------|
| 1 — Patient Overview | Title + subtitle + bullets | PatientHistory, PatientStatus: demographics, FIGO stage, molecular profile |
| 2 — Clinical Findings | Two-column: bullets + chart | Pathology, Radiology, tumor markers: histology, IHC, imaging, marker trend chart |
| 3 — Treatment & Trials | Bullets + trial list | ClinicalGuidelines, ClinicalTrials, MedicalResearch: NCCN recs, trials, consensus |

## Quick Reference

| Task | Code |
|------|------|
| Load template | `Presentation('tumor_board_slides.pptx')` |
| Access slide | `prs.slides[0]` (slides are pre-created in template) |
| Find shape by name | `for s in slide.shapes: if s.name == "body": ...` |
| Set text | `tf = shape.text_frame; tf.clear(); run = tf.paragraphs[0].add_run(); run.text = "..."` |
| Add bullet | `p = tf.add_paragraph(); p.space_after = Pt(6); run = p.add_run(); run.text = "..."` |
| Add image | `slide.shapes.add_picture(BytesIO_buf, left, top, width, height)` |
| Set font | `run.font.size = Pt(14); run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)` |
| Save to bytes | `buf = BytesIO(); prs.save(buf)` |

## Named Shapes in Template

### Slide 1 (Patient Overview)
- `title` — patient name + cancer type (white on navy)
- `subtitle` — FIGO stage + molecular profile (teal)
- `body` — 6 bullet points
- `footer` — "GYN Oncology Tumor Board"

### Slide 2 (Clinical Findings)
- `title` — "Pathology & Imaging Findings" (white on navy)
- `body_left` — 6 bullet points (left column)
- `chart_title` — marker name (teal)
- `chart_area` — placeholder shape (replaced by PNG chart image)

### Slide 3 (Treatment & Trials)
- `title` — "Treatment Plan & Clinical Trials" (white on navy)
- `body` — 6 treatment recommendation bullets
- `trials_header` — "Eligible Clinical Trials" (teal)
- `trials_body` — max 3 trial entries

## Tumor Marker Chart Embedding

```python
# 1. Generate matplotlib chart
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(dates, values, marker="o", color="#007C91")
ax.axhline(y=ref_upper, color="#CC0000", linestyle="--")

# 2. Save to BytesIO
buf = BytesIO()
plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
plt.close(fig)
buf.seek(0)

# 3. Replace placeholder shape
sp = chart_placeholder._element
left, top, width, height = chart_placeholder.left, chart_placeholder.top, ...
sp.getparent().remove(sp)
slide.shapes.add_picture(buf, left, top, width, height)
```

## Content Summarization (Risk Mitigation)

Content is **always** summarized via LLM before rendering to prevent overflow:

```python
settings = AzureChatPromptExecutionSettings(
    temperature=0.0,
    response_format=SlideContent,  # Enforces bullet count + word limits
)
```

`SlideContent` dataclass (in `tumor_board_summary.py`):
- `overview_bullets`: max 6 items
- `findings_bullets`: max 6 items
- `treatment_bullets`: max 6 items
- `trial_entries`: max 3 items

Fallback: if LLM parsing fails, truncate raw data to 80 chars per bullet.

## Critical Rules

- **Always use `Inches()` or `Pt()`** for dimensions — never raw EMU values
- **Max 6 bullets per slide, max 20 words per bullet** — enforced by SlideContent schema
- **Use `model_supports_temperature()`** before setting temperature
- **Save via blob storage** (`chat_artifact_accessor.write()`), never local filesystem
- **Chart is optional** — if no tumor marker data parses, skip chart (leave placeholder or blank)
- **Color palette**: Navy `#1B365D`, Teal `#007C91`, Dark text `#333333`

## Regenerating the Template

```bash
python scripts/generate_pptx_template.py
# Output: src/scenarios/default/templates/tumor_board_slides.pptx
```

## Files

| File | Purpose |
|------|---------|
| `src/scenarios/default/tools/presentation_export.py` | Main plugin |
| `src/scenarios/default/templates/tumor_board_slides.pptx` | Slide template |
| `scripts/generate_pptx_template.py` | Template generator |
| `src/data_models/tumor_board_summary.py` | SlideContent dataclass |
