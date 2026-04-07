---
status: pending
priority: p2
issue_id: "208"
tags: [code-review, performance, database]
dependencies: []
---

# AACT Database Opens New Connection Per Query

## Problem Statement
Every `aact_search` call executes `asyncpg.connect()` creating a new TCP connection to the remote AACT PostgreSQL server at `aact-db.ctti-clinicaltrials.org`, performs a single query, then closes. Each call pays full TCP + TLS handshake cost (200-500ms).

## Findings
- **File**: `src/mcp_servers/clinical_trials_mcp.py`, lines 509-514
- External host with network latency — handshake overhead is significant
- Multiple AACT queries per patient (different conditions, eligibility filters)
- The file already has a lazy `_http_session` singleton pattern (lines 93-107) that should be replicated

## Proposed Solution
Use `asyncpg.create_pool()` with a lazy singleton pattern. Pool size of 2-3 is sufficient.

- **Effort**: Small (~20 lines)
- **Impact**: Saves 200-500ms per AACT query

## Acceptance Criteria
- [ ] AACT queries use connection pool instead of per-query `connect()`
- [ ] Pool is lazily created on first use
- [ ] Pool is closed on application shutdown
