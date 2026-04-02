---
status: complete
priority: p2
issue_id: "023"
tags: [code-review, python-quality, maintainability, tumor-markers, caboodle]
dependencies: [020]
---

## Problem Statement

CA-125 is represented as three separate string literals in `caboodle_file_accessor.py`'s `marker_names` list: `"ca-125"`, `"ca125"`, and `"ca 125"`. Similarly, other markers have multiple variant strings. This list is rebuilt on every call to `get_tumor_markers()` (it's defined inline, not as a class constant) and the presence of 3 identical-meaning strings for the same marker indicates a normalization gap.

The real fix is to normalize the `ComponentName` field from Epic Caboodle before matching, rather than enumerating all possible spellings in application code.

```python
# Current — fragile enumeration:
marker_names = [
    "ca-125", "ca125", "ca 125",   # 3 variants for one marker
    "he4", "he 4",                  # 2 variants
    "hcg", "beta-hcg", "beta hcg", "quant b-hcg",  # 4 variants
    ...
]
```

## Findings

- **File:** `src/data_models/epic/caboodle_file_accessor.py` lines 172–184 (`get_tumor_markers`)
- **Reported by:** code-simplicity-reviewer (P2), performance-oracle (P3 — rebuilt every call)
- **Severity:** P2 — fragile string matching; new Epic site with different ComponentName format will silently miss markers

## Proposed Solutions

### Option A (Recommended): Normalize ComponentName before matching
```python
# Class-level constant (not rebuilt every call):
_TUMOR_MARKER_PATTERNS = re.compile(
    r"\b(ca[-\s]?125|he[-\s]?4|h?cg|beta[-\s]?hcg|cea|afp|alpha[-\s]?feto|ldh|scc|inhibin)\b",
    re.IGNORECASE
)

async def get_tumor_markers(self, patient_id: str) -> list[dict]:
    labs = await self._read_file(patient_id, "lab_results")
    return [
        lab for lab in labs
        if self._TUMOR_MARKER_PATTERNS.search(
            lab.get("ComponentName", lab.get("component_name", ""))
        )
    ]
```
- **Pros:** Single regex handles all variants; compiled once at class definition; robust to hyphen/space/no-separator variants; faster than `any(marker in ...)` loop
- **Cons:** Regex harder to read than a list; needs testing
- **Effort:** Small
- **Risk:** Low (same markers matched, more robustly)

### Option B: Move list to class constant (minimum fix)
```python
class CaboodleFileAccessor:
    _TUMOR_MARKER_NAMES = frozenset([
        "ca-125", "ca125", "ca 125",
        # ...
    ])
```
Stops list rebuild on every call; no other behavior change.
- **Effort:** Tiny
- **Risk:** None

## Recommended Action

Option B immediately (prevents list rebuild, trivial change). Option A as a follow-up when doing the constants consolidation (todo 020).

## Technical Details

- **Affected file:** `src/data_models/epic/caboodle_file_accessor.py` lines 172–184
- **Pattern:** `marker_names` local variable in `get_tumor_markers()` → class-level constant

## Acceptance Criteria

- [ ] `marker_names` list is a class-level constant (`_TUMOR_MARKER_NAMES = frozenset(...)`)
- [ ] Not rebuilt on every `get_tumor_markers()` call
- [ ] All existing variants still present (no regression)
- [ ] (Stretch) Regex normalization handles all hyphen/space/no-separator variants

## Work Log

- 2026-04-02: Identified by code-simplicity-reviewer and performance-oracle during code review
- 2026-04-02: Resolved — _TUMOR_MARKER_NAMES is already a frozenset class constant at caboodle_file_accessor.py:76.
