---
status: pending
priority: p2
issue_id: "180"
tags: [code-review, security, defense-in-depth]
dependencies: []
---

# Use validated nct_id instead of raw trial parameter in display URL

## Problem Statement
`display_more_information_about_a_trial` appends the raw `trial` parameter to the display URL instead of the regex-validated `nct_id`. While the regex validation currently runs before the URL construction, this creates a defense-in-depth gap: if the validation logic is ever refactored or bypassed, the raw input flows directly into a URL, creating a potential injection vector (open redirect, XSS via crafted URL).

## Findings
- **Source**: Security Sentinel (M-2)
- `src/scenarios/default/tools/clinical_trials.py:308-309` -- URL constructed with `self.clinical_trial_display + trial` instead of `+ nct_id`

## Proposed Solutions
1. **Replace `trial` with `nct_id` in URL construction**
   - Change `self.clinical_trial_display + trial` to `self.clinical_trial_display + nct_id`
   - Pros: Uses the validated, sanitized value; defense-in-depth; trivial change
   - Cons: None -- `nct_id` is already extracted and validated by the same method
   - Effort: ~2 minutes

## Acceptance Criteria
- [ ] Display URL uses `nct_id` (the regex-validated value) instead of `trial` (raw input)
- [ ] URL still correctly resolves to the ClinicalTrials.gov trial page
- [ ] No behavioral change for valid NCT IDs
- [ ] All existing clinical trials tests pass
