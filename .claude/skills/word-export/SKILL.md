---
name: word-export
description: Use this skill when generating GYN tumor board Word documents from agent outputs. Covers docxtpl template rendering, InlineImage embedding, clinical data formatting, and blob storage save patterns.
---

# Word Export for GYN Tumor Board

## Overview
Generates `.docx` tumor board reports using `docxtpl` (jinja2 templating on Word documents).
The template lives at `src/scenarios/default/templates/tumor_board_template.docx`.

## Quick Reference

| Task | Approach |
|------|----------|
| Load template | `DocxTemplate(template_path)` |
| Render | `doc.render(doc_data)` — pass dict of template variables |
| Inline images | `InlineImage(doc, stream_or_path, height=Inches(1.7))` |
| Hyperlinks | `RichText(text, color="#0000ee", underline=True, url_id=doc.build_url_id(url))` |
| Save to bytes | `stream = BytesIO(); doc.save(stream)` |
| Save to blob | `ChatArtifact(artifact_id, data=stream.getvalue())` → `chat_artifact_accessor.write(artifact)` |

## Template Variables

```python
doc_data = {
    "patient_id": str,
    "patient_gender": str,
    "patient_age": str,
    "medical_history": str,
    "social_history": str,
    "cancer_type": str,
    "figo_stage": str,              # GYN-specific
    "molecular_profile": str,       # GYN-specific
    "tumor_markers": str,           # GYN-specific
    "surgical_findings": str,       # GYN-specific
    "ct_scan_findings": list[str],
    "x_ray_findings": list[str],
    "pathology_findings": list[str],
    "treatment_plan": str,
    "board_discussion": str,        # GYN-specific
    "clinical_summary": list[str],  # LLM-generated
    "clinical_timeline": list[dict],# from PatientTimeline artifact
    "clinical_trials": list[dict],  # RichText with url_id
    "research_papers": list[dict],  # RichText with url_id
    "timeline_images": list[InlineImage],
    "radiology_images": list[InlineImage],
    "pathology_images": list[InlineImage],
}
```

## Plugin Pattern

```python
from data_models.plugin_configuration import PluginConfiguration

def create_plugin(plugin_config: PluginConfiguration):
    return ContentExportPlugin(
        kernel=plugin_config.kernel,
        chat_ctx=plugin_config.chat_ctx,
        data_access=plugin_config.data_access,
    )
```

## Critical Rules

- **Always load patient timeline artifact** before rendering — it populates `clinical_summary` and `clinical_timeline`
- **Use `model_supports_temperature()`** before setting `temperature=0` on AzureChatPromptExecutionSettings
- **Save via blob storage** (`chat_artifact_accessor.write()`), never to local filesystem
- **Use `get_chat_artifacts_url(blob_path)`** to generate the download link returned to the user
- **Structured output**: Use `response_format=ClinicalSummary` for LLM summarization to enforce schema
- **Temp directory cleanup**: Always use `tempfile.TemporaryDirectory()` with try/finally for timeline images

## Files

| File | Purpose |
|------|---------|
| `src/scenarios/default/tools/content_export/content_export.py` | Main plugin |
| `src/scenarios/default/tools/content_export/timeline_image.py` | Timeline visualization |
| `src/scenarios/default/templates/tumor_board_template.docx` | Word template |
| `src/data_models/tumor_board_summary.py` | ClinicalSummary, ClinicalTrial dataclasses |
| `src/data_models/chat_artifact.py` | ChatArtifact, ChatArtifactIdentifier |
