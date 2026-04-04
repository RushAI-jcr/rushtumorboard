---
name: No pre-commit hook to block PHI from entering git
description: No code-level guard prevents real patient GUIDs from being committed to the repo; gitignore is the only protection
type: security
status: complete
priority: p1
issue_id: "025"
tags: [security, hipaa, phi, git, pre-commit]
---

## Problem Statement

The `.gitignore` excludes `infra/patient_data/` (the real patient folder tree), but there is
no automated check that prevents a developer from accidentally including a real patient GUID
in source code, test data, config, or comments. A single line like
`patient_id = "8048FA31-..."` in a Python file would silently bypass gitignore.

**Risk:** A real GUID committed and pushed to GitHub (even a private repo) creates a
permanent HIPAA audit trail issue. GUIDs are patient identifiers — their presence in source
code constitutes PHI in the repo.

## Proposed Solution

A git `pre-commit` hook that scans staged additions for any of the 15 known real patient GUIDs.
If a match is found, the commit is blocked with a clear error message.

**Files:**
- `scripts/git-hooks/pre-commit` — committed hook source (checked in, shareable)
- `scripts/install-hooks.sh` — one-command installer for new clones
- `.git/hooks/pre-commit` — locally installed hook (not tracked by git)

## Acceptance Criteria

- [x] `scripts/git-hooks/pre-commit` script checks all 15 real patient GUIDs
- [x] Hook installed at `.git/hooks/pre-commit` and executable
- [x] Commit containing a real GUID is blocked with a clear error message
- [x] `scripts/install-hooks.sh` installs all hooks from `scripts/git-hooks/`

## Work Log

- 2026-04-02: Implemented. Hook scans staged additions for any of the 15 real GUIDs using
  a single grep with OR pattern. Blocks commit and reports which file contains the GUID.
  Installed locally. Shareable via scripts/install-hooks.sh.
