---
status: complete
priority: p1
issue_id: "002"
tags: [code-review, bug, slide-3-chart]
dependencies: []
---

# P1 — CA-125 chart never renders: wrong JSON key in `_parse_markers_raw`

## Problem Statement

`_parse_markers_raw` in `presentation_export.py` looks for `"markers"` or `"results"` keys
in the tumor marker JSON, but `get_tumor_marker_trend` returns data under `"data_points"`.
The function always returns `None` for real patient data, so Slide 3 permanently renders as
a single-column treatment history with no chart — even when CA-125 data exists and was
passed in.

## Findings

**`presentation_export.py` `_parse_markers_raw`, lines ~231–245:**
```python
data = data.get("markers", data.get("results", []))
```

**`tumor_markers.py` `get_tumor_marker_trend` actual return shape:**
```json
{
  "patient_id": "...",
  "marker": "CA-125",
  "data_points": [{"date": "2025-09-01", "value": 420.0, "unit": "U/mL"}],
  "analysis": {...}
}
```

The key is `"data_points"`, not `"markers"` or `"results"`. Additionally,
`get_all_tumor_markers` returns a dict keyed by marker name (not a list), which also fails
the `isinstance(data, list)` check at line 244.

**Impact:** Slide 3 chart is silently absent for every real patient. The two-column
chart layout (the main visual differentiator from the plain Word doc) never triggers.

## Proposed Solution

```python
@staticmethod
def _parse_markers_raw(tumor_markers_str: str) -> list[dict] | None:
    if not tumor_markers_str:
        return None
    try:
        data = json.loads(tumor_markers_str)
    except (json.JSONDecodeError, TypeError):
        return None
    # Handle single-marker shape from get_tumor_marker_trend
    if isinstance(data, dict):
        data = data.get("data_points",                  # get_tumor_marker_trend
               data.get("markers",                       # legacy key
               data.get("results", [])))                 # legacy key
        # get_all_tumor_markers returns {marker_name: {data_points: [...]}}
        if isinstance(data, dict):
            # grab the first marker's data_points list
            first = next(iter(data.values()), {})
            data = first.get("data_points", []) if isinstance(first, dict) else []
    if not isinstance(data, list) or len(data) < 2:
        return None
    return data
```

## Acceptance Criteria
- [ ] CA-125 chart renders on Slide 3 when `get_tumor_marker_trend` output is passed
- [ ] `get_all_tumor_markers` output also yields a parseable list (first marker wins)
- [ ] `_parse_markers_raw` docstring documents the expected input shapes
- [ ] Smoke test updated to verify chart renders for real `data_points` shape
