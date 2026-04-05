---
status: complete
priority: p1
issue_id: "197"
tags: [code-review, security]
dependencies: []
---

# Strengthen Path Traversal Protection with resolve() Check

## Problem Statement

The path separator check in `local_dev_stubs.py` (added in todo 192) rejects `/` and `\` in patient_id/filename but does NOT handle `..` sequences, null bytes, or symlink following. Standard defense is `resolve()` + prefix verification.

## Findings

**Flagged by:** Security Sentinel (H-1)

Current code (line 58):
```python
if any(sep in pid for sep in ("/", "\\")) or any(sep in fname for sep in ("/", "\\")):
```

Missing checks:
- `..` (dot-dot) traversal: `"..%2F..%2Fetc%2Fpasswd"` passes slash check
- Null bytes: `"\x00"` can truncate paths at OS level
- Symlink following: `mkdir(parents=True)` follows existing symlinks
- No `resolve()` post-join verification

## Proposed Solutions

### Option A: resolve() + startswith check (Recommended)
```python
base_dir = (Path.home() / "Desktop" / "dev testing").resolve()
dest_dir = (base_dir / pid).resolve()
if not str(dest_dir).startswith(str(base_dir)):
    logger.warning("Rejected artifact write: path escapes base directory")
    return
dest_file = (dest_dir / fname).resolve()
if not str(dest_file).startswith(str(dest_dir)):
    logger.warning("Rejected artifact write: filename escapes patient directory")
    return
```
Also add: `if "\x00" in pid or "\x00" in fname: return`

- Effort: Small | Risk: None

## Acceptance Criteria

- [x] Path validated with `resolve()` + `startswith()` prefix check
- [x] Null byte rejection added
- [x] Previous slash check removed (resolve handles it)

## Work Log

- 2026-04-04: Created from code review (Security Sentinel)
- 2026-04-04: Fixed — resolve() + startswith() prefix check, null byte rejection, slash check removed
