---
status: pending
priority: p3
issue_id: "159"
tags: [code-review, simplicity, quality]
dependencies: []
---

# Collapse Conditional Dict Building in clinical_trials.py

## Problem Statement

13 sequential `if value: structured_patient_data[key] = value` blocks at lines 275-298. Repetitive and error-prone (one key maps `grade` to `tumor_grade`).

## Proposed Solutions

Replace with dict comprehension:
```python
_OPTIONAL_FIELDS = {
    "platinum_sensitivity": platinum_sensitivity,
    "platinum_free_interval": platinum_free_interval,
    # ... etc
}
structured_patient_data.update({k: v for k, v in _OPTIONAL_FIELDS.items() if v})
```

## Work Log
- 2026-04-02: Identified during code review (code-simplicity-reviewer)
