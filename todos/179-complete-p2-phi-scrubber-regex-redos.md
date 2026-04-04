---
status: pending
priority: p2
issue_id: "179"
tags: [code-review, security, regex]
dependencies: []
---

# Bound \S+ in PHI scrubber ISO date regex to prevent ReDoS

## Problem Statement
The ISO date pattern `re.compile(r'\b\d{4}-\d{2}-\d{2}(?:T\S+)?\b')` in `phi_scrubber.py` uses unbounded `\S+` which could cause excessive backtracking (ReDoS) on adversarial or malformed input. In a healthcare application processing untrusted clinical text, this is a denial-of-service vector that could stall PHI scrubbing and block downstream processing.

## Findings
- **Source**: Security Sentinel (M-4)
- `src/utils/phi_scrubber.py:15` -- ISO date regex pattern with unbounded `\S+`

## Proposed Solutions
1. **Bound the match with a character limit**
   - Change `(?:T\S+)?` to `(?:T\S{1,30})?`
   - ISO 8601 timestamps with timezone are at most ~25 characters after the `T`, so 30 is generous
   - Pros: Simple fix, eliminates backtracking risk, no false negatives for valid ISO dates
   - Cons: Theoretical edge case of very long non-standard timestamps (not valid ISO anyway)
   - Effort: ~5 minutes

2. **Use a more specific time pattern**
   - Replace `\S+` with `\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?`
   - Pros: Matches only valid ISO 8601 timestamps, no backtracking risk
   - Cons: More complex regex, could miss non-standard timestamp formats in clinical data
   - Effort: ~15 minutes

## Acceptance Criteria
- [ ] `\S+` in the ISO date pattern is bounded (e.g., `\S{1,30}`)
- [ ] Pattern still matches standard ISO 8601 datetime strings (e.g., `2024-01-15T14:30:00Z`, `2024-01-15T14:30:00-05:00`)
- [ ] ReDoS test: input of `2024-01-15T` followed by 10,000 non-space characters completes in < 10ms
- [ ] All existing PHI scrubber tests pass
- [ ] No regression in PHI detection accuracy
