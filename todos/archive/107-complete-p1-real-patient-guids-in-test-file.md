---
status: complete
priority: p1
issue_id: "107"
tags: [code-review, security, phi, git]
dependencies: []
---

# 107 — Production Patient GUIDs Hardcoded in Committed Test File

## Problem Statement

Fifteen production patient GUIDs (UUID format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) are hardcoded at module level in `src/tests/test_local_agents.py:661-677` in a list named `REAL_GUIDS`. These values are committed to git and therefore permanently embedded in repository history. Even if the data behind these GUIDs is anonymized in the test environment, the GUIDs themselves are patient identifiers: in Epic, a patient GUID is a stable foreign key that links to the full medical record. Possessing the GUID is sufficient to query the FHIR API for the patient's clinical notes if the caller has network access and valid credentials.

The existing pre-commit hook scans for data files (CSV, JSON blobs) but does not scan Python source files for UUID patterns, meaning this category of exposure bypasses the current PHI detection layer entirely.

## Findings

- `src/tests/test_local_agents.py:661-677` — `REAL_GUIDS = ["xxxxxxxx-...", ...]` with 15 entries at module level.
- The GUIDs are used in test functions that call live FHIR endpoints. Their presence in source code is incidental to their use in tests — they could be loaded from a gitignored file without loss of test functionality.
- Pre-commit hook does not include a pattern matching `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` in `.py` files.
- Git history now contains these identifiers permanently. Rotating the GUIDs is not possible (Epic assigns them), so history rewrite is the only remediation.

## Proposed Solution

1. **Move `REAL_GUIDS` out of source into a gitignored fixture file.** Create `src/tests/local_patient_ids.json` (add to `.gitignore`). Load at test time:

   ```python
   import json, os, pathlib

   _FIXTURE = pathlib.Path(__file__).parent / "local_patient_ids.json"
   REAL_GUIDS: list[str] = (
       json.loads(_FIXTURE.read_text()) if _FIXTURE.exists()
       else os.environ.get("TEST_PATIENT_GUIDS", "").split(",")
   )
   ```

   Tests that require real GUIDs skip automatically if neither the fixture file nor the env var is present.

2. **Extend the pre-commit hook** to scan Python source files (including `src/tests/`) for UUID4-pattern strings:

   ```bash
   grep -rE "['\"][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}['\"]" src/ \
     && echo "ERROR: UUID literal found in source file — move to gitignored fixture" && exit 1
   ```

3. **Rewrite git history** to remove the GUIDs from all prior commits. Use `git filter-repo --path src/tests/test_local_agents.py --force` followed by a targeted content replacement, or `git filter-repo --replace-text expressions.txt`. Coordinate with all contributors to rebase or re-clone after the history rewrite.

4. **Add `src/tests/local_patient_ids.json` to `.gitignore`** alongside other local-only test assets.

## Acceptance Criteria

- [ ] No patient GUIDs appear in any committed source or test file (verified by running the pre-commit UUID scan)
- [ ] `REAL_GUIDS` is loaded from a gitignored `local_patient_ids.json` or `TEST_PATIENT_GUIDS` environment variable
- [ ] Tests that require real GUIDs are skipped (not failed) when neither the file nor env var is present
- [ ] Pre-commit hook extended to scan `src/` Python files for UUID-pattern string literals
- [ ] GUIDs removed from git history via `git filter-repo` or equivalent; all contributors notified to re-clone
