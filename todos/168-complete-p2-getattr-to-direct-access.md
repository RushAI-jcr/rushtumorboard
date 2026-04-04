---
status: complete
priority: p2
issue_id: "168"
tags: [code-review, python, quality]
dependencies: []
---

# Replace getattr() with Direct Attribute Access for patient_demographics

## Problem Statement

Both export files use `getattr(self.chat_ctx, "patient_demographics", None)` to access demographics. Since `patient_demographics` is declared in `ChatContext.__init__` (line 16), it always exists. `getattr` is misleading — it implies the attribute might not exist, which is false. Every other ChatContext attribute is accessed directly.

## Findings

- **Source**: Python Reviewer (HIGH), Code Simplicity (LOW), Architecture Strategist (noted)
- **Files**: `src/scenarios/default/tools/content_export/content_export.py:224`, `src/scenarios/default/tools/presentation_export.py:201`

## Proposed Solutions

Replace `getattr(self.chat_ctx, "patient_demographics", None)` with `self.chat_ctx.patient_demographics` in both files. Two lines changed, zero risk.

## Acceptance Criteria

- [ ] No `getattr` for `patient_demographics` in export files
- [ ] Direct attribute access used consistently

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | 3 reviewers flagged |
