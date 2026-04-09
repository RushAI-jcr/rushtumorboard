---
status: pending
priority: p2
issue_id: "230"
tags: [code-review, quality]
dependencies: []
---

# Narrow Bare except Exception in _build_mrn_index_sync

## Problem Statement

`_build_mrn_index_sync` in `caboodle_file_accessor.py` catches `except Exception` at DEBUG level when scanning patient folders for MRN mappings. This swallows file permission errors, encoding errors, and other actionable failures silently.

## Findings

**Flagged by:** Kieran Python Reviewer (HIGH)

**File:** `src/data_models/epic/caboodle_file_accessor.py`

```python
except Exception:
    logger.debug("Could not read demographics for %s", folder.name)
```

## Proposed Solutions

### Option A: Narrow to expected exceptions + WARNING (Recommended)
```python
except (FileNotFoundError, KeyError, csv.Error, UnicodeDecodeError) as exc:
    logger.warning("Could not read demographics for %s: %s", folder.name, exc)
```
- Effort: Small | Risk: None

## Acceptance Criteria

- [ ] Exception clause narrowed to expected types
- [ ] Log level raised to WARNING
- [ ] Unexpected exceptions propagate naturally

## Work Log

- 2026-04-09: Created from Phase 2 code review (Kieran Python Reviewer)
