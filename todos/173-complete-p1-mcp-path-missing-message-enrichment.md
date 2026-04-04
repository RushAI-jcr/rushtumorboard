---
status: pending
priority: p1
issue_id: "173"
tags: [code-review, agent-native, parity, mcp]
dependencies: []
---

# MCP/Copilot Studio Path Missing Message Enrichment

## Problem Statement

When agents are invoked through the MCP endpoint (`src/mcp_app.py`), responses are returned raw — `append_links()` and `apply_sas_urls()` from `utils/message_enrichment.py` are never called. This means patient images, clinical trial links, and SAS-signed download URLs are silently dropped for MCP/Copilot Studio consumers.

The Teams bot path (`assistant_bot.py:146-147`) and WebSocket path (`chats.py:174-175`) both correctly apply enrichment. The MCP path is the only delivery channel that drops these features.

## Findings

- **Source**: Agent-Native Reviewer (P0 Critical)
- **File**: `src/mcp_app.py:59-82` — response loop returns raw `response.content` without enrichment
- **Comparison**: `src/bots/assistant_bot.py:146-147` and `src/routes/api/chats.py:174-175` both call `append_links()` + `apply_sas_urls()`

## Proposed Solutions

### Option A: Add enrichment to mcp_app.py (Recommended)
Import and call `append_links` and `apply_sas_urls` in the MCP response loop.

```python
from utils.message_enrichment import append_links, apply_sas_urls

# Inside process_chat() response loop:
content = append_links(response.content, chat_ctx)
content = await apply_sas_urls(content, chat_ctx, data_access)
```

- **Pros**: Direct fix, matches other channels
- **Cons**: MCP consumers may not render HTML — enrichment may need to be adapted for non-HTML channels
- **Effort**: Small (15 min)

## Acceptance Criteria

- [ ] MCP path applies append_links() and apply_sas_urls() to agent responses
- [ ] Patient images, trial links, and SAS URLs appear in MCP responses
- [ ] Consider whether MCP consumers handle HTML or need a different format
