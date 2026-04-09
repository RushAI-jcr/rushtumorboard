---
status: pending
priority: p2
issue_id: "229"
tags: [code-review, quality, radiology]
dependencies: ["226"]
---

# Remove 17 Redundant Keywords from layer3_keywords

## Problem Statement

Because `layer3_keywords` uses substring matching (`kw in text.lower()`), shorter keywords automatically match any note containing longer variants. For example, "mri" matches "mri pelvis", "mri abdomen", "mri brain", "mri spine", "pelvic mri", and "mri ap" — making all 6 longer variants redundant.

## Findings

**Flagged by:** Code Simplicity Reviewer (identified specific list), Performance Oracle

**File:** `src/scenarios/default/tools/radiology_extractor.py` — `layer3_keywords` tuple

**Redundant keywords (subsumed by shorter ones already in the list):**

| Redundant keyword | Subsumed by |
|---|---|
| "mri pelvis" | "mri" |
| "mri abdomen" | "mri" |
| "mr pelvis" | "mri" (partial — "mr" not in list) |
| "mri brain" | "mri" |
| "mri spine" | "mri" |
| "pelvic mri" | "mri" |
| "mri ap" | "mri" |
| "transvaginal us" | "transvaginal" |
| "pelvic ultrasound" | "ultrasound" |
| "renal ultrasound" | "ultrasound" |
| "pelvic us" | (NOT redundant — "us" too short to be a keyword) |
| "renal us" | (NOT redundant — same reason) |
| "fdg-pet" | "fdg" |
| "fdg pet" | "fdg" |
| "chest x-ray" | "x-ray" |
| "ct cap w" | "ct cap" |
| "us pelvis" | (NOT redundant — "us" alone isn't a keyword) |

**Actually redundant: ~14 keywords** (not 17 — "pelvic us", "renal us", "us pelvis" are NOT redundant since "us" alone would be too generic).

Note: "mr pelvis" — "mr" isn't a standalone keyword, but "mri" won't match "mr pelvis". Keep "mr pelvis" OR add "mr " (with space).

## Proposed Solutions

### Option A: Remove clearly redundant, keep ambiguous ones (Recommended)
Remove the ~12 keywords that are definitively subsumed. Keep "mr pelvis", "pelvic us", "renal us", "us pelvis".
- Effort: Small | Risk: None

## Acceptance Criteria

- [ ] Redundant keywords removed
- [ ] No false negatives introduced (verify "mr pelvis" case)
- [ ] Tuple has clear comments explaining why shorter keywords subsume longer ones

## Work Log

- 2026-04-09: Created from Phase 2 code review (Code Simplicity Reviewer)
