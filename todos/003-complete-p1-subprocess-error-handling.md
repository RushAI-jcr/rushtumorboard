---
status: complete
priority: p1
issue_id: "003"
tags: [code-review, reliability, hipaa, error-handling]
dependencies: []
---

# P1 — Three error-handling gaps in the subprocess/blob pipeline

## Problem Statement

Three distinct failure modes in `presentation_export.py` either produce a silent wrong
result, leak PHI into logs, or go entirely undetected (blob upload).

## Findings

**A — stdout discarded; Node errors may be silent (`line ~188`):**
```python
_, stderr = await proc.communicate(input=js_input.encode())
```
PptxGenJS and its deps can write to stdout (via `console.log`). Unhandled JS exceptions
sometimes write to stdout instead of stderr. If Node exits non-zero but stderr is empty
and stdout has the error text, the returned error message will be blank.

Fix: use both streams:
```python
stdout, stderr = await proc.communicate(input=js_input.encode())
if proc.returncode != 0:
    err_text = (stderr or stdout or b"").decode(errors="replace")
    raise RuntimeError(f"PPTX render failed (exit {proc.returncode}): {err_text[:400]}")
```

**B — Empty file check missing (`line ~202`):**
```python
with open(tmp_path, "rb") as f:
    pptx_bytes = f.read()
```
If Node exits 0 but writes nothing (race condition on disk, `writeFile` callback never
fired), `pptx_bytes` is `b""` and an empty blob is uploaded silently.

Fix: `if not pptx_bytes: raise RuntimeError("PPTX renderer produced an empty file")`

**C — Blob upload failure completely unhandled (`line ~216`):**
```python
await self.data_access.chat_artifact_accessor.write(artifact)
```
`write()` calls Azure Blob `upload_blob` which raises `HttpResponseError`,
`ServiceRequestError`, etc. None are caught. An unhandled exception here returns a 500
to the user with no useful message and the PPTX bytes are lost with no retry path.

Fix: wrap in `try/except Exception as exc` and return a user-facing error string with
enough detail to diagnose (storage account name, not the full exception which may contain
tokens).

**D — PHI potentially logged (`line ~199`, HIPAA concern):**
```python
logger.error("tumor_board_slides.js failed: %s", err)
```
`err` is raw stderr from the Node process. While unlikely under normal failures, a future
version of the script could echo back the input JSON (which contains patient name, stage,
genetics) in a verbose error. Log only the first 200 chars and strip at a safe boundary.

Fix:
```python
logger.error("tumor_board_slides.js exited %d — check stderr for details", proc.returncode)
```
Never log the content of `err` at ERROR level in a HIPAA context.

## Acceptance Criteria
- [x] stdout is captured alongside stderr; both used to construct error text
- [x] Empty `pptx_bytes` raises a `RuntimeError` before blob upload is attempted
- [x] Blob upload failure is caught and returns a user-facing error string (not a 500)
- [x] `logger.error` call does not include raw stderr content
- [x] TOCTOU in `finally` block replaced: `os.unlink` wrapped in `try/except FileNotFoundError`
