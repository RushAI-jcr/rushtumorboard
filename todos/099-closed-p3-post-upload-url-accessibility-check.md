---
status: closed
priority: p3
issue_id: "099"
tags: [code-review, agent-native, reliability]
dependencies: []
---

# P3 — No post-upload URL accessibility check; `export_to_word_doc` blob write unguarded

## Problem Statement

Both export tools construct and return a download URL without verifying the artifact is accessible at that URL. If the blob container access policy blocks access, CDN propagation is slow, or the URL template is wrong, the download link returned to the Teams chat will be dead — with no indication at export time.

## Findings

Agent-native reviewer: "Neither tool verifies that the uploaded artifact is accessible at the returned URL. The agent receives a URL and presents it to the user."

The download URL is a FastAPI-proxied route (`/chat_artifacts/...`), not a direct Azure Blob URL. Accessibility depends on the app being running, the route existing, and the blob actually being written. These are typically reliable, but a misconfigured `BACKEND_APP_HOSTNAME` or a stale app deployment can produce a permanently dead link.

This is P3 because there are no known production failures from this pattern — it is a defence-in-depth gap.

## Proposed Solution

After successful `write()`, perform a lightweight HEAD request to the constructed URL:

```python
import aiohttp
async with aiohttp.ClientSession() as session:
    try:
        async with session.head(output_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status >= 400:
                logger.warning("Generated artifact URL returned %d (conv=%s)", resp.status, self.chat_ctx.conversation_id)
    except Exception:
        pass  # Don't fail export for a HEAD check failure; just log
```

Alternatively: add the return URL to a background verification queue that notifies the user if the link is inaccessible after 30 seconds.

## Acceptance Criteria
- [ ] Post-upload HEAD check performed (or background verification queued)
- [ ] Failed HEAD check logged at WARNING level with conversation_id (not patient_id)
- [ ] Export still succeeds if HEAD check fails (non-blocking verification)
- [ ] `export_to_word_doc` blob write receives same try/except as PPTX (see also todo 090)
