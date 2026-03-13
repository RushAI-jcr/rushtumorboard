---
name: pptx-export
description: Generate GYN tumor board 3-slide PowerPoint presentations using python-pptx
---

# PPTX Export for GYN Tumor Board

Generate a 3-slide `.pptx` per patient using `python-pptx` with template from `scripts/generate_pptx_template.py`.

## 3-Slide Layout
1. **Patient Overview**: title + subtitle (FIGO/molecular) + 6 bullets (demographics, history)
2. **Clinical Findings**: left bullets (pathology/radiology) + right chart (tumor marker trend PNG)
3. **Treatment & Trials**: 6 treatment bullets + 3 trial entries

## Workflow
1. Summarize agent outputs via LLM with `response_format=SlideContent` (enforces max 6 bullets, 20 words each)
2. Generate tumor marker chart: `matplotlib` -> `BytesIO` -> `slide.shapes.add_picture()`
3. Load template, find shapes by name (`title`, `body`, `body_left`, `chart_area`, `trials_body`)
4. Set text via `text_frame.clear()` + `add_run()`, bullets via `add_paragraph()`
5. Save to blob storage via `ChatArtifact`

## Key Files
- Plugin: `src/scenarios/default/tools/presentation_export.py`
- Template: `src/scenarios/default/templates/tumor_board_slides.pptx`
- Generator: `scripts/generate_pptx_template.py`
- Model: `src/data_models/tumor_board_summary.py` (SlideContent)

## Rules
- Colors: Navy `#1B365D`, Teal `#007C91`, Dark text `#333333`
- Use `model_supports_temperature()` before setting temperature
- Always `plt.close(fig)` in try/finally for chart generation
- Save via blob storage, never local filesystem
