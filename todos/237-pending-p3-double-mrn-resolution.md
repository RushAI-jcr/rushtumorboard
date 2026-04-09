---
status: pending
priority: p3
issue_id: "237"
tags: [code-review, architecture]
dependencies: ["231"]
---

# Double MRN Resolution in patient_data.py and _read_file

## Problem Statement

`resolve_patient_id` is called in both `patient_data.py:load_patient_data` (line 130) AND `caboodle_file_accessor.py:_read_file` (line 620). Every file read resolves the ID twice — once upstream, once in the accessor. The second call always hits the fast path (`os.path.isdir`) so cost is negligible, but the dual responsibility creates maintenance confusion.

## Findings

**Flagged by:** Kieran Python (#2), Security Sentinel (#3), Architecture Strategist (#2B), Performance Oracle (#5)

Both calls are defensible:
- `patient_data.py` needs resolution to set `chat_ctx.patient_id` to the canonical GUID
- `_read_file` provides defense-in-depth for callers that bypass `load_patient_data`

## Proposed Solutions

### Option A: Keep both, add docstring clarification (Recommended)
Add a comment to `_read_file` explaining the intentional idempotent resolution as defense-in-depth.
- Effort: Tiny | Risk: None

### Option B: Remove from _read_file, require callers to resolve
- Effort: Small | Risk: Low — but loses defense-in-depth

## Acceptance Criteria

- [ ] Docstring or comment explains why resolution happens in two places

## Work Log

- 2026-04-09: Created from code review (4 agents flagged)
