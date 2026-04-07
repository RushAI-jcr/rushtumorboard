---
status: pending
priority: p2
issue_id: "214"
tags: [code-review, architecture, deployment]
dependencies: []
---

# No Health Check or Readiness Probe

## Problem Statement
The application starts and accepts requests without verifying the data accessor can reach its backend. No `/health` or `/readyz` endpoint exists. If `CLINICAL_NOTES_SOURCE=fabric` but the Fabric endpoint is down, the first user request fails with unhandled error.

## Findings
- **File**: `src/app.py` — no health check route
- **File**: `src/data_models/data_access.py` — no startup probe
- Critical for Azure App Service / AKS container orchestration

## Proposed Solution
Add `/health` endpoint that:
1. Returns `{"status": "ok", "accessor": "FabricClinicalNoteAccessor", "methods": [...]}` on success
2. Calls `accessor.get_patients()` as a lightweight probe
3. Returns 503 if probe fails

- **Effort**: Small (~20 lines)

## Acceptance Criteria
- [ ] `/health` endpoint returns accessor status
- [ ] Returns 503 when backend is unreachable
- [ ] Suitable for container health check configuration
