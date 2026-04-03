---
status: pending
priority: p3
issue_id: "132"
tags: [code-review, performance, async]
dependencies: []
---

# 132 — Blocking `os.path.exists` calls on the asyncio event loop thread

## Problem Statement

`caboodle_file_accessor.py:298-300` calls `os.path.exists(parquet_path)` and `os.path.exists(csv_path)` directly inside the `async` method `_read_file`, running those filesystem stat syscalls on the asyncio event loop thread. On network-mounted storage (Azure Files, NFS), a single stat call can block for tens of milliseconds. `get_metadata_list` fans out via `asyncio.gather` for 3 concurrent calls — each of those concurrent coroutines blocks the event loop with its own stat call, stalling all other async work for the duration.

## Findings

- `caboodle_file_accessor.py:298-300` — two bare `os.path.exists()` calls inside `async def _read_file`

## Proposed Solution

Wrap each call in `run_in_executor` to move the blocking syscall off the event loop thread:

```python
loop = asyncio.get_running_loop()
parquet_exists = await loop.run_in_executor(None, os.path.exists, parquet_path)
csv_exists = await loop.run_in_executor(None, os.path.exists, csv_path)
```

Alternatively, use `pathlib.Path.stat()` inside an executor. This is consistent with how CSV reads are already handled elsewhere in the accessor (dispatched via executor).

## Acceptance Criteria

- [ ] Both `os.path.exists` calls in `_read_file` are wrapped with `run_in_executor`
- [ ] The asyncio event loop thread is not blocked by filesystem stat syscalls during concurrent `asyncio.gather` execution
- [ ] Behavior is unchanged on local disk; improvement is observable on network-mounted storage
