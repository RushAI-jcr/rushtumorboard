---
title: "CA-125 Chart Missing in PPTX When get_all_tumor_markers Used as Input"
problem_type: logic-errors
component: "PPTX export pipeline — tumor_markers plugin + presentation_export._parse_markers_raw"
symptoms:
  - "CA-125 chart does not render in tumor board PowerPoint (blank chart area, no error raised)"
  - "Only occurs when data comes from get_all_tumor_markers, not get_tumor_marker_trend"
  - "data_points key missing from per-marker summary dict returned by get_all_tumor_markers"
  - "elif branch in _parse_markers_raw never triggers: all(isinstance(v, dict)) returns False because patient_id maps to a string"
  - "Fallback else branch returns a nested dict instead of a list, so chart data is silently empty"
  - "Pre-commit linter reverts both fixes, re-introducing the regression"
tags:
  - ca125
  - tumor-markers
  - pptx-export
  - presentation_export
  - linter-regression
  - json-unwrap
  - type-guard
  - get_all_tumor_markers
  - get_tumor_marker_trend
severity: high
related_files:
  - src/scenarios/default/tools/tumor_markers.py
  - src/scenarios/default/tools/presentation_export.py
related_docs:
  - docs/solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md
  - docs/solutions/integration-issues/gyn-tumor-board-adaptation.md
---

## CA-125 Chart Missing in PPTX When `get_all_tumor_markers` Used as Input

### Problem Description

The CA-125 trend chart fails to render in PowerPoint exports when the `tumor_markers` slide input is sourced from `get_all_tumor_markers` rather than `get_tumor_marker_trend`. The chart silently produces no output — no error is raised, the slide is generated, but the chart area is blank.

This affects any workflow that calls `get_all_tumor_markers` and pipes the result directly into the PPTX export pipeline.

---

### Root Cause Analysis

The failure has two independent causes that compound each other.

#### Cause 1 — Missing `data_points` in `get_all_tumor_markers` summary output

`get_all_tumor_markers` in `tumor_markers.py` builds a per-marker summary dict for each detected marker. That dict contained statistical fields (`count`, `nadir`, `peak`, `trend`, etc.) but omitted the raw `"data_points"` list. The PPTX chart renderer (`_parse_markers_raw` in `presentation_export.py`) requires the raw data point list to draw any chart. Without it, there is nothing to plot.

#### Cause 2 — Broken type-guard in `_parse_markers_raw`

The parser used a type-guard condition to detect the multi-marker envelope shape:

```python
elif data and all(isinstance(v, dict) for v in data.values()):
```

This checks whether every value in the top-level dict is itself a dict, which holds for a clean marker dict like `{"CA-125": {...}, "HE4": {...}}`. However, `get_all_tumor_markers` returns an envelope with a scalar field:

```json
{"patient_id": "abc123", "markers": {"CA-125": {"count": 5, "data_points": [...], ...}}}
```

Because `"patient_id"` maps to a string (not a dict), `all(isinstance(v, dict) for v in data.values())` evaluates to `False`. The code falls through to the `else` branch:

```python
data = data.get("markers", data.get("results", []))
```

This returns `{"CA-125": {...}}` — a dict, not a list. The final `isinstance(data, list)` check fails and `_parse_markers_raw` returns `None`. No chart is drawn.

#### Output shapes from the two plugin functions

```
get_tumor_marker_trend  →  {"marker": "CA-125", "data_points": [...], "analysis": {...}}
get_all_tumor_markers   →  {"patient_id": "...", "markers": {"CA-125": {"data_points": [...], ...}}}
```

Any parser that treats these as the same shape will fail on one of them.

---

### The Two-Part Fix

#### Fix 1 — Add `data_points` to the per-marker summary dict (`tumor_markers.py`)

In `get_all_tumor_markers`, append `"data_points": points` as the final field of the `summaries[name]` dict:

```python
# Before (missing data_points — linter reverts to this):
summaries[name] = {
    "count": len(points),
    "first_value": values[0] if values else None,
    "first_date": points[0]["date"] if points else None,
    "latest_value": values[-1] if values else None,
    "latest_date": points[-1]["date"] if points else None,
    "nadir": min(values) if values else None,
    "peak": max(values) if values else None,
    "unit": points[0]["unit"] if points else "",
    "trend": self._simple_trend(values),
}

# After (correct — data_points required for chart rendering):
summaries[name] = {
    "count": len(points),
    "first_value": values[0] if values else None,
    "first_date": points[0]["date"] if points else None,
    "latest_value": values[-1] if values else None,
    "latest_date": points[-1]["date"] if points else None,
    "nadir": min(values) if values else None,
    "peak": max(values) if values else None,
    "unit": points[0]["unit"] if points else "",
    "trend": self._simple_trend(values),
    "data_points": points,  # required for chart rendering — do not remove
}
```

#### Fix 2 — Replace the fragile type-guard in `_parse_markers_raw` (`presentation_export.py`)

```python
# Before (broken — fails when any top-level value is a scalar):
if "data_points" in data:
    data = data["data_points"]
elif data and all(isinstance(v, dict) for v in data.values()):
    first = next(iter(data.values()), {})
    data = first.get("data_points", [])
else:
    data = data.get("markers", data.get("results", []))

# After (correct):
if "data_points" in data:
    data = data["data_points"]
else:
    # get_all_tumor_markers: {"patient_id": "...", "markers": {"CA-125": {...}}}
    # "patient_id" maps to a str, so all(isinstance(v, dict)) is False — unwrap explicitly
    inner = data.get("markers", data.get("results", data))
    if isinstance(inner, dict):
        first = next(iter(inner.values()), {})
        data = first.get("data_points", []) if isinstance(first, dict) else []
    else:
        data = inner
```

---

### Key Insight: Why `all(isinstance(v, dict))` Is Fragile

The guard `all(isinstance(v, dict) for v in data.values())` works only for "pure" marker dicts where every key maps to a sub-dict. It silently breaks the moment any top-level scalar field is present. Common culprits in this codebase: `patient_id`, `marker`, `error`, `status`.

**The rule:** When parsing JSON with multiple possible shapes, discriminate on the presence of a well-known structural key (`"markers"`, `"data_points"`, etc.), never on the runtime types of all values.

```python
# Fragile:
if all(isinstance(v, dict) for v in data.values()):
    ...

# Robust:
if "markers" in data:
    ...
elif "data_points" in data:
    ...
```

---

### Linter Reversion Warning

Two lines in this fix are at high risk of silent reversion by the pre-commit linter.

**Line 1 — `"data_points": points` in `tumor_markers.py`**

Static analysis may flag `points` as assigned but never used after the linter rewrites the summary dict construction. The field is not dead — it is the sole source of raw chart data for the PPTX renderer.

- Protect with inline comment: `"data_points": points,  # required for chart rendering — do not remove`
- Regression test: call `get_all_tumor_markers` for any patient with CA-125 data and check that the returned dict for each marker contains a non-empty `data_points` list.

**Line 2 — The explicit `inner = data.get("markers", ...)` unwrap block in `presentation_export.py`**

The linter may collapse this back to the shorter `all(isinstance(v, dict))` guard. That revert reintroduces the scalar-field bug.

- Protect with the explanatory comment documenting `patient_id` as the reason the type-guard fails.
- Regression test: pass `get_all_tumor_markers` output directly to `_parse_markers_raw` and assert the result is not `None`.

---

### Prevention Strategies

#### 1. Add targeted regression tests

```python
# tests/test_parse_markers_raw.py

SAMPLE_POINTS = [
    {"date": "2024-01-15", "value": 450.0, "unit": "U/mL"},
    {"date": "2024-04-01", "value": 210.0, "unit": "U/mL"},
]

TREND_SHAPE = {
    "marker": "CA-125",
    "data_points": SAMPLE_POINTS,
    "analysis": {"trend": "declining significantly"},
}

ALL_MARKERS_SHAPE = {
    "patient_id": "GUID-ABCD-1234",   # string at top level — the bug trigger
    "markers": {
        "CA-125": {"data_points": SAMPLE_POINTS, "unit": "U/mL", "latest_value": 210.0},
    },
}

def test_trend_shape_returns_data_points():
    result = _parse_markers_raw(json.dumps(TREND_SHAPE))
    assert result is not None
    assert len(result) == len(SAMPLE_POINTS)

def test_all_markers_shape_with_string_top_level_key():
    """
    Regression: patient_id (str) at top level must NOT break type-guard detection.
    Previously all(isinstance(v, dict)) returned False for this shape.
    """
    result = _parse_markers_raw(json.dumps(ALL_MARKERS_SHAPE))
    assert result is not None, (
        "Parser returned None for all-markers shape — likely caused by "
        "isinstance type guard rejecting mixed-type top-level dict"
    )

def test_all_markers_missing_data_points_returns_none():
    """Linter may strip data_points from per-marker dict — ensure graceful handling."""
    payload = {
        "patient_id": "GUID-0001",
        "markers": {"CA-125": {"unit": "U/mL", "latest_value": 210.0}},
    }
    result = _parse_markers_raw(json.dumps(payload))
    assert result is None or result == []
```

#### 2. Use `TypedDict` to make `data_points` an explicit contract

Once the return type is declared, the linter cannot treat `data_points` as unused:

```python
from typing import TypedDict

class MarkerPoint(TypedDict):
    date: str
    value: float
    unit: str

class MarkerSummary(TypedDict):
    data_points: list[MarkerPoint]  # linter: required key, not dead code
    unit: str
    latest_value: float | None
    trend: str
```

#### 3. Schema consistency (long-term)

The root complexity in `_parse_markers_raw` exists because the two plugin functions return structurally dissimilar shapes. A `normalize_marker_response(raw: dict) -> NormalizedMarkerPayload` adapter that both functions pass through before returning would eliminate all branching in the parser. Both shapes would produce a canonical `{"data_points": [...], "marker": "..."}` and `_parse_markers_raw` reduces to a single code path.

---

### Related Files

- [`src/scenarios/default/tools/tumor_markers.py`](https://github.com/RushAI-jcr/rushtumorboard/blob/main/src/scenarios/default/tools/tumor_markers.py)
- [`src/scenarios/default/tools/presentation_export.py`](https://github.com/RushAI-jcr/rushtumorboard/blob/main/src/scenarios/default/tools/presentation_export.py)

### Related Docs

- [`docs/solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md`](../data-issues/multi-layer-fallback-csv-caching-strategy.md) — 3-layer fallback and caching for `tumor_markers.py`; tightly coupled with this issue as the upstream data source
- [`docs/solutions/integration-issues/gyn-tumor-board-adaptation.md`](../integration-issues/gyn-tumor-board-adaptation.md) — Original creation of `presentation_export.py` and the CA-125 chart requirement
