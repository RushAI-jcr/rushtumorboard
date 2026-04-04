---
name: json-decode-error-not-logged-fabric-accessor
description: JSONDecodeError is caught but never logged in fabric_clinical_note_accessor.py, causing silent data loss for notes with non-JSON content in production
type: code-review
status: complete
priority: p2
issue_id: 053
tags: [code-review, reliability, logging, data-quality]
---

## Problem Statement

`fabric_clinical_note_accessor.py:118-130`: `except json.JSONDecodeError as e:` — the exception variable `e` is bound but never logged. The comment says "Try to handle note content that is not JSON" but there is no operator visibility into when this happens. If `note_content` is falsy, `note_json` stays as `{}` and a note with no content is silently returned as a valid (empty) note — silent data loss for that specific note. In production, JSON decode failures in clinical notes indicate a data pipeline problem.

## Findings

- `fabric_clinical_note_accessor.py:118-130`: `except json.JSONDecodeError as e:` — `e` bound but never used or logged
- When `json.JSONDecodeError` is raised, execution continues silently with `note_json = {}`
- If `note_content` is falsy (empty string, `None`), `note_json` is `{}` and a note with no fields is returned as a valid note object
- The calling code in `read_all` has no way to distinguish a valid empty note from a silently-failed parse
- In production, JSON decode failures indicate: Fabric API returning malformed data, encoding issues in the pipeline, or API contract changes
- No `logger.warning` or `logger.error` call means operators have no telemetry signal when this occurs

## Proposed Solutions

### Option A
Add a `logger.warning` call inside the `except json.JSONDecodeError` block that logs the note ID and the exception: `logger.warning("Note %s: non-JSON content, using plain-text fallback: %s", note_id, e)`. This gives operators visibility into decode failures without raising an exception that would abort the batch.

**Pros:** Immediate operator visibility via Azure Application Insights; includes both note ID (for triage) and exception message (for diagnosis); does not change runtime behavior (still returns best-effort note); one-line fix
**Cons:** `note_id` may itself be PHI-adjacent — confirm whether Fabric note IDs are safe to log; logs may become noisy if the Fabric API consistently returns non-JSON for certain note types
**Effort:** Trivial (< 15 minutes)
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/data_access/fabric_clinical_note_accessor.py` (lines 118-130)

## Acceptance Criteria

- [ ] `except json.JSONDecodeError as e:` block logs a warning including the exception message `e`
- [ ] Warning includes the note identifier (confirm it is not PHI before logging in full, or truncate)
- [ ] Warning log is visible in Azure Monitor telemetry
- [ ] If `note_content` is falsy, the empty-note case is also logged distinctly from the JSON decode error case
- [ ] Unit test: mock a Fabric API response with non-JSON content and assert the warning is logged

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
