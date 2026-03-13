---
name: word-export
description: Generate GYN tumor board Word documents using docxtpl template rendering
---

# Word Export for GYN Tumor Board

Generate `.docx` reports using `docxtpl` with template at `src/scenarios/default/templates/tumor_board_template.docx`.

## Workflow
1. Load template: `DocxTemplate(template_path)`
2. Build `doc_data` dict with GYN fields: `figo_stage`, `molecular_profile`, `tumor_markers`, `surgical_findings`, `board_discussion`
3. Add images: `InlineImage(doc, stream, height=Inches(1.7))`
4. Add trial links: `RichText(text, url_id=doc.build_url_id(url))`
5. Render: `doc.render(doc_data)`
6. Save to blob: `ChatArtifact(artifact_id, data=BytesIO().getvalue())` via `chat_artifact_accessor.write()`

## Key Files
- Plugin: `src/scenarios/default/tools/content_export/content_export.py`
- Template: `src/scenarios/default/templates/tumor_board_template.docx`
- Models: `src/data_models/tumor_board_summary.py` (ClinicalSummary, ClinicalTrial)

## Rules
- Use `model_supports_temperature()` before setting `temperature=0`
- Save via blob storage, never local filesystem
- Use `response_format=ClinicalSummary` for LLM summarization
- Use `tempfile.TemporaryDirectory()` with try/finally for timeline images
