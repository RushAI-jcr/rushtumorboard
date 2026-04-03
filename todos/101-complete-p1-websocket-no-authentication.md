---
status: complete
priority: p1
issue_id: "101"
tags: [code-review, security, authentication, phi]
dependencies: []
---

# 101 — WebSocket Endpoint Accepts Connections Without Authentication

## Problem Statement

The WebSocket endpoint `/api/ws/chats/{chat_id}/messages` (defined in `src/routes/api/chats.py:112-199`) accepts any caller without authentication. The Teams bot code path has Bot Framework JWT validation, but the React client WebSocket path has no equivalent check. Any network-reachable client — including a compromised browser tab, an SSRF exploit, or any host on the hospital LAN — can open a WebSocket, supply an arbitrary `patient_id`, and receive full agent responses that include PHI extracted from clinical notes and FHIR resources. Additionally, line 127 logs full message content (including `patient_id` and clinical content) at INFO level, permanently writing PHI into application logs.

## Findings

- `src/routes/api/chats.py:112-199` — WebSocket handler. No authentication check before or after `await websocket.accept()`. The upgrade handshake is completed for every caller unconditionally.
- Line 127: `logger.info(f"Message content: {content}, sender: {sender}, mentions: {mentions}")` — `content` includes the user's chat message and `mentions` includes agent names that may reveal patient context. Logged at INFO means this reaches Application Insights and any configured log sink.
- The Teams bot path (same file, HTTP POST handler) validates Bot Framework tokens via `BotFrameworkAdapter`. The WebSocket path has no parallel mechanism.
- `chat_id` and `patient_id` values appear in prior WebSocket frames and log entries, making them enumerable by any observer of those channels.

## Proposed Solution

1. **Validate EasyAuth principal before accepting the WebSocket upgrade.** Azure App Service EasyAuth strips the `X-MS-CLIENT-PRINCIPAL-ID` header from unauthenticated requests at the platform level. Check this header before calling `websocket.accept()`:

   ```python
   principal_id = websocket.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
   if not principal_id:
       await websocket.close(code=1008)  # 1008 = Policy Violation
       return
   ```

   Closing before `accept()` causes the HTTP upgrade to fail with 403, which is visible to the caller.

2. **Downgrade message content log from INFO to DEBUG.** Replace the `logger.info` at line 127 with `logger.debug`. Debug logs should be disabled in production log sinks by default:

   ```python
   logger.debug(f"Message received: sender={sender}, mention_count={len(mentions or [])}")
   ```

   Do not log `content` at any level above DEBUG. Do not log `patient_id` in the same log line as message content.

3. **Add a unit/integration test** that opens a WebSocket connection without the `X-MS-CLIENT-PRINCIPAL-ID` header and asserts the connection is rejected (close code 1008 or HTTP 403 before upgrade).

## Acceptance Criteria

- [ ] WebSocket upgrade is rejected (close code 1008 or HTTP 403) when `X-MS-CLIENT-PRINCIPAL-ID` header is absent
- [ ] `logger.info` on message content at line 127 changed to `logger.debug`
- [ ] `content` is not logged at INFO or WARNING level anywhere in the WebSocket handler
- [ ] Unauthenticated WebSocket connection never reaches `await websocket.accept()`
- [ ] A test verifies that a connection without a valid principal header is rejected before the session begins
