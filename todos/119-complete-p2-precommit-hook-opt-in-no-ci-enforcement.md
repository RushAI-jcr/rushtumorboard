---
status: pending
priority: p2
issue_id: "119"
tags: [code-review, security, phi, devops]
dependencies: []
---

# 119 — PHI GUID pre-commit hook is opt-in only with no CI enforcement backstop

## Problem Statement

The pre-commit hook that blocks real patient GUIDs from being committed must be manually installed per clone (`cp scripts/git-hooks/pre-commit .git/hooks/pre-commit`). Git hooks are not enforced by the repository — any developer who clones and skips installation, or who passes `git commit --no-verify`, bypasses protection entirely. The hook also scans only staged content and hardcodes 15 specific GUIDs, meaning any new real patient GUID added to test fixtures is unblocked until the allowlist is manually extended.

## Findings

- `scripts/git-hooks/pre-commit` — the GUID-scanning hook; not auto-installed
- `scripts/install-hooks.sh` — optional installation script; not called by any CI or onboarding automation
- No GitHub Actions workflow runs GUID scanning on pushed commits or PRs

## Proposed Solution

1. Add a GitHub Actions CI workflow (`.github/workflows/phi-scan.yml`) that runs on every `push` and `pull_request` event. The workflow step should:
   - Run the same GUID-pattern scan against all files in the repository (not just staged files)
   - Fail the job if any known patient GUID pattern is matched
   - Use `git diff origin/main...HEAD` to scope scans on PRs, full repo scan on pushes to protected branches
2. Register the known GUID patterns as GitHub custom secret scanning patterns to catch them before merge.
3. Update `CLAUDE.md` (or `README`) to document that CI is the mandatory enforcement layer and the local hook is optional fast-feedback.
4. Retain the local pre-commit hook as-is; do not remove it.

## Acceptance Criteria

- [ ] A GitHub Actions workflow runs the GUID scan on every push and pull_request event
- [ ] CI fails with a clear error message if any committed file contains a known patient GUID pattern
- [ ] The local pre-commit hook is retained and documented as an optional fast-feedback tool
- [ ] `install-hooks.sh` or onboarding docs clarify that CI is the authoritative enforcement layer
