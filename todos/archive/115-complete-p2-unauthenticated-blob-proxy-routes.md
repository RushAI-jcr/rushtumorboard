---
status: complete
priority: p2
issue_id: "115"
tags: [code-review, security, authentication, phi]
dependencies: []
---

# 115 — Blob proxy routes serve artifacts with no authentication check

## Problem Statement

Routes `/chat_artifacts/{blob_path:path}` and `/patient_data/{blob_path:path}` in `patient_data_routes.py` proxy arbitrary blob paths from Azure Blob Storage with no authentication. Blob paths follow the predictable pattern `{conversation_id}/{patient_id}/{filename}`, which is derivable from the chat flow. Any HTTP client that can guess or reconstruct a blob path can download any patient artifact — including generated Word documents and PPTX slides containing PHI — without presenting credentials. The `:path` converter allows slashes, enabling traversal across conversation boundaries.

## Findings

- `src/routes/patient_data/patient_data_routes.py:42-48` — both proxy route handlers; no EasyAuth check, no principal validation, no prefix guard before the blob download call

## Proposed Solution

1. Before serving any blob, verify an authenticated EasyAuth principal is present (check `X-MS-CLIENT-PRINCIPAL` header or equivalent; return 401 if absent).
2. Parse the authenticated user's `conversation_id` from the principal claims.
3. Validate that `blob_path` starts with the authenticated `conversation_id` prefix — reject with 403 if it does not.
4. Keep the existing blob streaming logic intact after the two guard checks pass.

Example guard:

```python
principal = get_authenticated_principal(request)  # raises 401 if missing
if not blob_path.startswith(f"{principal.conversation_id}/"):
    raise HTTPException(status_code=403, detail="Forbidden")
```

## Acceptance Criteria

- [ ] Unauthenticated requests to both blob proxy routes return 401
- [ ] Authenticated requests for blobs outside the caller's `conversation_id` prefix return 403
- [ ] Authenticated requests for blobs within the caller's `conversation_id` prefix continue to succeed
- [ ] No change to blob streaming behavior for legitimate callers
