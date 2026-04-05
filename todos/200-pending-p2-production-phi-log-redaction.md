---
status: complete
priority: p2
issue_id: "200"
tags: [code-review, security, hipaa]
dependencies: []
---

# Redact Patient GUIDs from Production Blob Accessor Logs

## Problem Statement

The production `ChatArtifactAccessor` logs `blob_path` which contains patient_id (a real patient GUID) in f-string log messages. These flow to Azure Application Insights via Azure Monitor. Under HIPAA, patient identifiers in application logs constitute potential PHI exposure.

## Findings

**Flagged by:** Security Sentinel (H-2)

Pre-existing issue (not introduced by this PR), but the local_dev_stubs.py fix (todo 192) shows the correct pattern.

**Affected file:** `src/data_models/chat_artifact_accessor.py` lines 38, 66, 76
```python
logger.info(f"Read artifact for {blob_path}. Duration: {time() - start}s")
logger.info(f"Wrote artifact for {blob_path}. Duration: {time() - start}s")
```

The `blob_path` format is `{base64_conv_id}/{patient_id}/{filename}`.

## Proposed Solutions

### Option A: Log only filename and truncated conversation ID (Recommended)
Replace blob_path with non-identifying components:
```python
logger.info("Read artifact %s. Duration: %ss", artifact_id.filename, time() - start)
```
- Effort: Small | Risk: None

## Acceptance Criteria

- [x] Production log messages do not contain patient GUIDs
- [x] Duration tracking preserved
- [x] Filename logged for debugging

## Work Log

- 2026-04-04: Created from code review (Security Sentinel — pre-existing issue)
- 2026-04-04: Fixed — Replaced blob_path in all 3 log messages with artifact_id.filename; archive log no longer includes conversation_id
