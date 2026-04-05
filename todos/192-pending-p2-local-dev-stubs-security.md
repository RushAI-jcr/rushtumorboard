---
status: complete
priority: p2
issue_id: "192"
tags: [code-review, security, hipaa]
dependencies: []
---

# Local Dev Stubs: Path Validation + PHI in Logs

## Problem Statement

`local_dev_stubs.py` writes artifacts to `~/Desktop/dev testing/{patient_id}/{filename}` without validating path components at this layer. Also logs full file paths containing patient GUIDs.

## Findings

**Path traversal (Security Sentinel):**
- `artifact.artifact_id.patient_id` and `filename` are unconstrained strings at the write layer
- Upstream `validate_patient_id()` blocks `/` but this layer has no defense
- File: `src/data_models/local_dev_stubs.py` lines 54-62

**PHI in logs (Security Sentinel):**
- `logger.info("Saved artifact to %s", dest_file)` logs patient GUID in path
- Same pattern exists in production `ChatArtifactAccessor` (pre-existing)
- If logs ship to Azure Monitor, this is a HIPAA concern

## Proposed Solutions

### Option A: Defensive validation + log redaction (Recommended)
- Add path separator check: reject if `/` or `\` in patient_id or filename
- Log only filename, not full path: `logger.info("Saved artifact %s", artifact.artifact_id.filename)`
- Effort: Small | Risk: None

### Option B: Resolve and verify path stays under base dir
- Use `Path.resolve()` and verify result starts with expected base dir
- More thorough but slightly more code
- Effort: Small | Risk: None

## Acceptance Criteria

- [x] `patient_id` containing path separators is rejected before filesystem write
- [x] Log messages do not contain patient identifiers in file paths
- [ ] Pre-existing `ChatArtifactAccessor` log messages also redacted (out of scope — production accessor, separate PR)

## Work Log

- 2026-04-04: Created from code review (Security Sentinel agent)
- 2026-04-04: Fixed — path separator validation + log redaction in local_dev_stubs.py
