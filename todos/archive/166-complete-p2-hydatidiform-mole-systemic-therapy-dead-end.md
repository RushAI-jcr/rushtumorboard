---
status: complete
priority: p2
issue_id: "166"
tags: [code-review, agent-native, gtn, nccn]
dependencies: []
---

# Hydatidiform Mole Systemic Therapy Returns Dead End

## Problem Statement

`_CANCER_TYPE_MAP` maps "hydatidiform mole" and "molar pregnancy" to `hydatidiform_mole`. The `_SYSTEMIC_PREFIXES` tuple has `"GTN-D"` but no `"HM-"` entry. A query like `get_nccn_systemic_therapy(cancer_type="hydatidiform mole", setting="primary")` will return the error branch: `"No systemic therapy pages found for hydatidiform mole"`.

This is misleading because hydatidiform mole management involves chemotherapy (single-agent methotrexate or actinomycin for post-molar GTN). The agent may incorrectly tell a clinician there are no systemic therapy options.

**Why:** The GTN case (`patient_gyn_gtn_001`) starts as a hydatidiform mole before becoming choriocarcinoma. An agent asking "what are the systemic therapy options for hydatidiform mole?" will hit this dead end rather than being guided to query "gtn".

**How to apply:** Either add `"HM-"` to `_SYSTEMIC_PREFIXES` (if HM pages contain chemotherapy tables) OR make the error response informative and route the agent to "gtn".

## Findings

**Source:** agent-native-reviewer

**Location:** `src/scenarios/default/tools/nccn_guidelines.py`

```python
_SYSTEMIC_PREFIXES: ClassVar[tuple[str, ...]] = (
    "ENDO-D", "VAG-D", "VULVA-E", "UTSARC-C",
    "OV-D", "LCOC-A", "LCOC-5A", "LCOC-5B",
    "CERV-F", "GTN-D",
    # Missing: "HM-" — hydatidiform mole pages
)
```

**GTN guideline JSON pages available:** HM-1, HM-2 (from manifest). Need to check if HM-D or similar systemic therapy pages exist in the loaded JSON.

## Proposed Solutions

### Option A: Check HM pages and add "HM-" prefix if they contain chemo content

```python
_SYSTEMIC_PREFIXES: ClassVar[tuple[str, ...]] = (
    "ENDO-D", "VAG-D", "VULVA-E", "UTSARC-C",
    "OV-D", "LCOC-A", "LCOC-5A", "LCOC-5B",
    "CERV-F", "GTN-D", "HM-",  # add if HM pages include chemo tables
)
```

- **Pros:** Technically correct if HM content covers chemo
- **Risk:** May include irrelevant pages if HM pages are surgical/monitoring only

### Option B: Add informative fallback message for hydatidiform_mole key (Recommended)

In `get_nccn_systemic_therapy`, add a disease-specific response when no therapy codes are found for `hydatidiform_mole`:

```python
if not therapy_codes:
    if disease_key == "hydatidiform_mole":
        return json.dumps({
            "cancer_type": cancer_type,
            "note": "Hydatidiform mole is primarily managed surgically (uterine evacuation). "
                    "For post-molar GTN requiring systemic therapy, query with cancer_type='gtn'. "
                    "GTN systemic therapy (methotrexate, actinomycin D, EMA-CO) is on GTN-D pages.",
        })
    # ... existing generic error
```

- **Pros:** Clinically accurate, guides agent to correct query
- **Effort:** Small
- **Risk:** None

### Option C: Map "hydatidiform mole" to "gestational_trophoblastic_neoplasia" in `_CANCER_TYPE_MAP`

Change the alias so both mole and GTN use the same disease key (and thus same GTN-D systemic therapy pages). Clinically imprecise but practically useful.

## Recommended Action

_(Leave blank — fill during triage)_

## Technical Details

- **Affected file:** `src/scenarios/default/tools/nccn_guidelines.py`
- Check HM-1 and HM-2 content in `data/nccn_guidelines/gtn_v2.2026.json` for systemic therapy content

## Acceptance Criteria

- [ ] `get_nccn_systemic_therapy(cancer_type="hydatidiform mole", setting="primary")` returns either valid therapy content or a helpful routing message
- [ ] The agent is never told "no options found" when options exist under a related disease key

## Work Log

- 2026-04-03: Identified by agent-native-reviewer during code review

## Resources

- `_SYSTEMIC_PREFIXES` in `nccn_guidelines.py` lines 96–100
- GTN guideline pages: `data/nccn_guidelines/gtn_v2.2026.json` (HM-1, HM-2)
