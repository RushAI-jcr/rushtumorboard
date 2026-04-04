---
status: complete
priority: p2
issue_id: "165"
tags: [code-review, agent-native, nccn, llm-contract]
dependencies: []
---

# @kernel_function Descriptions Don't List New Cancer Type Aliases

## Problem Statement

Semantic Kernel passes the `@kernel_function` description to the LLM as the function's advertised capability. The descriptions for `search_nccn_guidelines` and `get_nccn_systemic_therapy` still list only canonical cancer types and don't mention the 15+ new aliases added to `_CANCER_TYPE_MAP` (choriocarcinoma, cervix, vagina, hydatidiform mole, etc.).

An agent reasoning about a choriocarcinoma patient sees a function description that doesn't mention choriocarcinoma — it will be less likely to pass that term as `cancer_type`.

**Why:** The LLM uses the function description to decide how to call the tool. Undocumented aliases are accessible at the code level but invisible at the LLM-contract level, creating a gap between what works and what the model will use.

**How to apply:** Update `@kernel_function` description strings in `nccn_guidelines.py`.

## Findings

**Source:** agent-native-reviewer

**Location:** `src/scenarios/default/tools/nccn_guidelines.py`

```python
# search_nccn_guidelines description (line ~381):
"cancer_type: endometrial, vaginal, vulvar, uterine sarcoma, ovarian, cervical, or gtn"
# Missing: cervix, vagina, choriocarcinoma, hydatidiform mole, molar pregnancy, 
#          leiomyosarcoma, fallopian tube, peritoneal, germ cell, borderline ovarian, etc.

# get_nccn_systemic_therapy description (line ~494):
"cancer_type: endometrial, vaginal, vulvar, uterine_sarcoma, ovarian, cervical, or gtn"
# Same gap
```

## Proposed Solutions

### Option A: Enumerate key aliases inline (Recommended)

```python
@kernel_function(
    description=(
        "Search NCCN guidelines for GYN cancer treatment recommendations. "
        "cancer_type accepts: endometrial/uterine, vaginal/vagina, vulvar, "
        "uterine sarcoma/leiomyosarcoma, ovarian/fallopian tube/peritoneal, "
        "cervical/cervix, gtn/gestational trophoblastic/choriocarcinoma, "
        "or hydatidiform mole/molar pregnancy. "
        "clinical_question: the specific clinical scenario to look up."
    )
)
```

- **Pros:** Makes aliases discoverable to LLM, concise
- **Effort:** Small
- **Risk:** None

### Option B: Point to `_CANCER_TYPE_MAP` keys
Add a brief note: "See _CANCER_TYPE_MAP for full alias list."
- **Cons:** LLM can't read code, so this helps humans only

## Recommended Action

_(Leave blank — fill during triage)_

## Technical Details

- **Affected file:** `src/scenarios/default/tools/nccn_guidelines.py`
- Lines: `search_nccn_guidelines` `@kernel_function` description (~line 381), `get_nccn_systemic_therapy` description (~line 494)

## Acceptance Criteria

- [ ] `search_nccn_guidelines` description lists at least: cervix, choriocarcinoma, hydatidiform mole as accepted aliases
- [ ] `get_nccn_systemic_therapy` description updated similarly
- [ ] An agent asked about "choriocarcinoma" or "molar pregnancy" would see these terms in the tool description

## Work Log

- 2026-04-03: Identified by agent-native-reviewer during code review

## Resources

- `_CANCER_TYPE_MAP` in `nccn_guidelines.py` lines 48–83
