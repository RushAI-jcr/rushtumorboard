---
status: pending
priority: p1
issue_id: "100"
tags: [code-review, security, phi, authentication]
dependencies: []
---

# 100 — Unauthenticated `/view/` Routes Expose PHI

## Problem Statement

The routes `/view/{conversation_id}/{patient_id}/patient_timeline/...` and `/view/.../patient_data_answer/...` render and return full clinical note HTML with zero authentication. Both route files contain inline comments acknowledging they are "not meant for production," yet both are unconditionally registered in `src/app.py` at lines 79–80. Any HTTP client that can enumerate a `conversation_id` and `patient_id` — values that appear in logs, URLs, and WebSocket frames — can retrieve PHI without credentials of any kind.

## Findings

- `src/routes/views/patient_timeline_routes.py` — renders full clinical note HTML; no auth dependency injected.
- `src/routes/views/patient_data_answer_routes.py` — returns patient data answers as HTML; no auth dependency injected.
- `src/app.py:79-80` — both routers are registered unconditionally with `app.include_router(...)`. No feature flag, no environment guard, no middleware condition.
- Neither file imports any authentication utility. The "not meant for production" comments have not prevented deployment.
- `conversation_id` and `patient_id` values are present in application logs and WebSocket message payloads, making enumeration feasible for any internal network attacker.

## Proposed Solution

1. **Gate route registration** behind an explicit environment variable. In `src/app.py`, wrap both `include_router` calls:

   ```python
   if os.getenv("DEMO_ROUTES_ENABLED", "false").lower() == "true":
       app.include_router(patient_timeline_router)
       app.include_router(patient_data_answer_router)
   ```

   Default must be `false` (absent = disabled). This alone removes the attack surface from all production deployments.

2. **Add EasyAuth principal check** inside each route handler as a defense-in-depth layer. Before rendering any response, validate that the `X-MS-CLIENT-PRINCIPAL-ID` header is present and non-empty (Azure App Service EasyAuth injects this header for authenticated sessions and strips it from unauthenticated requests):

   ```python
   principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
   if not principal:
       raise HTTPException(status_code=401, detail="Authentication required")
   ```

3. **Remove the "not meant for production" comments** and replace them with a clear module-level docstring explaining the `DEMO_ROUTES_ENABLED` guard mechanism, so the intent is machine-enforced, not comment-enforced.

4. **Verify in CI** that the default application startup (no env overrides) does not register any `/view/` path. Add a test that iterates `app.routes` and asserts no route path begins with `/view/` when `DEMO_ROUTES_ENABLED` is unset.

## Acceptance Criteria

- [ ] `/view/` routes are not registered unless `DEMO_ROUTES_ENABLED=true` is explicitly set in the environment
- [ ] Requests to `/view/` endpoints require a valid authenticated principal (`X-MS-CLIENT-PRINCIPAL-ID` header present)
- [ ] Production deployments with `DEMO_ROUTES_ENABLED` unset return 404 on all `/view/` paths
- [ ] A CI test confirms no `/view/` route appears in `app.routes` under default configuration
- [ ] "Not meant for production" comments replaced with documented, enforced guard mechanism
