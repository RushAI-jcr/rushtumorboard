---
status: pending
priority: p3
issue_id: "220"
tags: [code-review, simplicity, dead-code]
dependencies: []
---

# Dead Code Cleanup (~265 LOC)

## Problem Statement
Multiple dead code paths and YAGNI violations identified across the codebase. None affect functionality but add cognitive overhead and maintenance burden.

## Findings

### Dead code to remove:
1. **`supported_methods()` + `_STUB_METHODS`** in `accessor_stub_mixin.py` (lines 20-43) — never called. ~15 LOC.
2. **Parquet support** in `caboodle_file_accessor.py` (lines 20-23, 461-462, 516-539) — no .parquet files exist, production path is Fabric. ~35 LOC.
3. **`graph_rag.py`** — not wired to any agent in agents.yaml. ~117 LOC.
4. **`create_json_response` + `DateTimeEncoder`** in `chats.py` (lines 22-25, 72-77) — defined but never used. ~10 LOC.
5. **`display_image_urls` rendering** in `message_enrichment.py` (lines 19-25) — field never populated. ~6 LOC.
6. **`HLS_MODEL_ENDPOINTS`** in `config.py` (lines 166-172) — parsed but never consumed. ~8 LOC.
7. **`healthcare_agents` branch** in `group_chat.py` (lines 44-45, 270-271, 335-340) — no agents.yaml entry uses it. ~8 LOC.

### Duplication to extract:
8. **Note-loading boilerplate** in `patient_data.py` (lines 157-171 vs 268-281) — identical in `create_timeline` and `process_prompt`. Extract `_load_and_cap_notes()`. ~15 LOC.
9. **MCP handler pattern** in `mcp_app.py` (lines 117-164 vs 169-203) — nearly identical. Extract factory. ~30 LOC.

## Acceptance Criteria
- [ ] Items 1-7 removed or quarantined
- [ ] Items 8-9 refactored to DRY
- [ ] All tests pass
