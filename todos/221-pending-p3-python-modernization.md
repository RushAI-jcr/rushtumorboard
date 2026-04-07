---
status: pending
priority: p3
issue_id: "221"
tags: [code-review, quality, python]
dependencies: []
---

# Python Modernization and Code Quality

## Problem Statement
Various Python quality improvements identified across the codebase. None are bugs but improve maintainability and type safety.

## Findings

1. **f-string logging**: Multiple files use `logger.info(f"...")` instead of `logger.info("%s", ...)`. Eager evaluation even when log level is above INFO. Files: `data_access.py:72,140`, `mcp_app.py:61,66,93,117-123`, `user.py:95`.

2. **Deprecated Pydantic v1 API**: `Message.dict()` in `chats.py:46-52` should be `.model_dump()` (Pydantic v2).

3. **ChatContext untyped attributes**: `patient_data`, `display_blob_urls`, `display_image_urls`, `display_clinical_trials`, `output_data` are all `list[Any]`. Should be typed for safety (`chat_context.py:17-24`).

4. **`or` comparison**: `data_access.py:133` uses `== "epic" or == "caboodle"` — should use `in ("epic", "caboodle")`.

5. **`frozenset([...])` vs `frozenset({...})`**: `caboodle_file_accessor.py:83` creates intermediate list.

6. **Module-level probe**: `group_chat.py:68-75` creates SK thread at import time — move to startup function.

7. **Teams "clear" trigger**: `assistant_bot.py:65` uses `.endswith("clear")` — fragile, "unclear" triggers it.

## Acceptance Criteria
- [ ] f-string logging replaced with %s formatting
- [ ] Pydantic v2 API used consistently
- [ ] ChatContext attributes typed
