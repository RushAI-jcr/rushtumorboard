---
status: pending
priority: p2
issue_id: "219"
tags: [code-review, agent-native, mcp]
dependencies: [203]
---

# Artifact Downloads Not Accessible via MCP

## Problem Statement
Export tools generate download URLs pointing to `https://{host}/chat_artifacts/{path}`. These are served by `patient_data_routes.py` under the FastAPI app at `/`. The MCP Starlette app is at `/mcp/`. An MCP consumer receives URLs but must make a separate HTTP GET — which requires auth the MCP caller doesn't provide. In production with auth enabled, artifact download returns 401.

## Findings
- **File**: `src/scenarios/default/tools/content_export/content_export.py`, line 431
- **File**: `src/scenarios/default/tools/presentation_export.py`, line 336
- MCP consumer gets URL in response text but can't download

## Proposed Solutions
1. Add MCP tool `download_artifact(filename)` returning raw bytes
2. Generate SAS-signed URLs that are self-authenticating
3. Mount artifact route under MCP Starlette app

- **Effort**: Medium

## Acceptance Criteria
- [ ] MCP consumers can retrieve generated Word/PPTX artifacts
