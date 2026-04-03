---
status: complete
priority: p2
issue_id: "129"
tags: [code-review, security, phi, logging]
dependencies: []
---

# 129 — Full HTTP headers and user message content logged at INFO severity

## Problem Statement

Two INFO-severity log lines expose PHI and credentials to Application Insights and any operator who reviews logs:

(A) `user.py:28`: `logger.info(f"Got request headers: {request.headers}")` logs all HTTP headers including `X-MS-CLIENT-PRINCIPAL` (a JWT containing the user's AAD object ID, email, and roles), `Authorization`, and `Cookie` headers. These appear in Application Insights at INFO severity and are routinely inspected.

(B) `chats.py:127`: `logger.info(f"Message content: {content}, sender: {sender}, mentions: {mentions}")` logs the complete text of every user chat message at INFO. Users routinely type patient identifiers, MRNs, and clinical queries directly into the chat input.

## Findings

- `src/routes/api/user.py:28` — full `request.headers` dict logged at INFO
- `src/routes/api/chats.py:127` — full `content` (user message text) logged at INFO

## Proposed Solution

(A) Remove the full-headers log line from `user.py:28`. If header tracing is needed for debugging, replace with a DEBUG-level log of only non-sensitive headers (e.g., `Content-Type`, `X-Request-Id`):

```python
logger.debug("Request headers (non-sensitive): content-type=%s", request.headers.get("content-type"))
```

(B) Remove message content from the `chats.py` INFO log. Replace with a non-PHI summary at DEBUG:

```python
logger.debug("Chat message received: length=%d, sender=%s, mention_count=%d", len(content), sender, len(mentions))
```

## Acceptance Criteria

- [ ] No full `request.headers` dict is logged at INFO or above anywhere in the codebase
- [ ] No user message `content` text is logged at INFO or above anywhere in the codebase
- [ ] Equivalent DEBUG-level logs retain useful non-PHI debugging information (lengths, counts, non-sensitive header values)
- [ ] Changes verified against all other logger calls in `user.py` and `chats.py` for similar patterns
