---
status: pending
priority: p3
issue_id: "141"
tags: [code-review, architecture, reliability]
dependencies: []
---

# 141 — NCCN data directory discovery relies on fragile hardcoded relative path traversal

## Problem Statement

`NCCNGuidelinesPlugin._find_data_dir()` in `nccn_guidelines.py:82-95` resolves the data directory by walking 4 levels up from `__file__` (`".." / ".." / ".." / ".." / "data" / "nccn_guidelines"`). This is brittle to any change in the module's location within the repository. The fallback uses `Path(os.getcwd()) / "data" / "nccn_guidelines"`, which breaks in containerized deployments where the working directory is not the repository root. Neither path is logged at startup, so failures surface as a missing-data error deep in the first request rather than at boot time.

## Findings

- `nccn_guidelines.py:82-95` — `_find_data_dir()` with 4-level `..` traversal and CWD fallback

## Proposed Solution

Add `NCCN_DATA_DIR` as the primary discovery mechanism, falling back to the current heuristic only for local development:

```python
@classmethod
def _find_data_dir(cls) -> Path:
    env_path = os.environ.get("NCCN_DATA_DIR")
    if env_path:
        resolved = Path(env_path)
        logger.info("NCCN data directory from env: %s", resolved)
        return resolved

    # Local development fallback
    candidate = Path(__file__).parent / ".." / ".." / ".." / ".." / "data" / "nccn_guidelines"
    resolved = candidate.resolve()
    logger.info("NCCN data directory from relative path: %s", resolved)
    return resolved
```

Document `NCCN_DATA_DIR` in the deployment environment variable reference.

## Acceptance Criteria

- [ ] `NCCN_DATA_DIR` environment variable is used as the primary data directory when set
- [ ] Startup log records which data directory path was resolved and its source (env var vs. heuristic)
- [ ] Containerized deployment with `NCCN_DATA_DIR` set correctly locates NCCN data without relying on CWD or relative traversal
- [ ] Local development without `NCCN_DATA_DIR` continues to work via the fallback
