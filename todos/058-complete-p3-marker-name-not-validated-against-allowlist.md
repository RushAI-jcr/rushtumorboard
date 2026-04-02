---
name: marker-name-not-validated-against-allowlist
description: LLM-supplied marker argument in get_tumor_marker_trend is used without validation against the GYN_MARKERS allowlist
type: code-review
status: pending
priority: p3
issue_id: 058
tags: [code-review, security, input-validation]
---

## Problem Statement

`tumor_markers.py:92` uses `marker.lower()` — a value supplied by the LLM agent via `get_tumor_marker_trend`'s `@kernel_function` — directly as a substring match keyword against clinical notes text without first validating it against the known allowlist of valid marker names. While there is no SQL injection or shell injection risk (the match is a pure Python `in` check), an empty string `""` matches every note in the corpus, and unrecognized marker names could produce arbitrarily broad or meaningless matches silently.

## Findings

`tumor_markers.py:92` (approximate):
```python
async def get_tumor_marker_trend(self, marker: str, ...) -> str:
    ...
    matches = [note for note in notes if marker.lower() in note.text.lower()]
```

The `GYN_MARKERS` dict (approximately line 30) defines the valid marker names recognized by this tool:
```python
GYN_MARKERS = {
    "ca125": ...,
    "ca19-9": ...,
    "cea": ...,
    ...
}
```

Edge cases not currently guarded:
- `marker = ""` — matches every note (all strings contain the empty string)
- `marker = "the"` — matches most notes due to common word presence
- `marker = "ca"` — matches both `ca125` and `ca19-9` notes, producing a merged/incorrect trend
- Unrecognized marker name returns results silently rather than an informative error

## Proposed Solutions

### Option A
Validate `marker` against `GYN_MARKERS.keys()` before use; return an informative error string if not recognized.

```python
normalized = marker.strip().lower()
if not normalized or normalized not in GYN_MARKERS:
    valid = ", ".join(sorted(GYN_MARKERS.keys()))
    return f"Unknown marker '{marker}'. Valid markers: {valid}."
```

**Pros:** Prevents empty-string and unrecognized-marker edge cases; returns actionable feedback to the LLM agent; uses the existing `GYN_MARKERS` dict as the single source of truth.
**Cons:** LLM must supply exact GYN_MARKERS key spelling; may need fuzzy matching if LLM uses synonyms (e.g., "CA-125" vs "ca125").
**Effort:** Small
**Risk:** Low

### Option B
Add a comment explaining why the marker argument is safe to use as-is (LLM input does substring matching only, not code execution), and document the empty-string edge case as a known limitation.

```python
# marker is LLM-supplied but used only for substring matching (no code execution risk).
# Known limitation: empty string matches all notes. The LLM is instructed to always
# supply a non-empty marker name via the kernel function description.
```

**Pros:** Zero behavioral change; documents intent.
**Cons:** Does not fix the empty-string edge case; relies on LLM instruction compliance.
**Effort:** Small
**Risk:** Low

## Technical Details

**Affected files:**
- `tumor_markers.py` (line 92 substring match; `GYN_MARKERS` dict definition ~line 30; `get_tumor_marker_trend` function signature)

## Acceptance Criteria

- [ ] Either: `marker` is validated against `GYN_MARKERS.keys()` before use, with an informative error returned for unrecognized or empty input
- [ ] Or: a comment is present at the usage site documenting the intentional lack of validation and the known empty-string edge case
- [ ] Empty string `""` does not silently match all notes (either rejected by validation or documented as out-of-scope)
- [ ] Existing tumor marker trend tests continue to pass

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
