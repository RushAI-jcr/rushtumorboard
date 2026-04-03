---
status: complete
priority: p3
issue_id: "139"
tags: [code-review, security, input-validation]
dependencies: []
---

# 139 — SSRF risk from unvalidated NCT ID in trial URL construction

## Problem Statement

`display_more_information_about_a_trial` in `clinical_trials.py:197` constructs a URL by concatenating the base URL with a `trial` parameter received from the LLM: `self.clinical_trial_url + trial`. No validation is applied to `trial` before the `aiohttp.ClientSession.get()` call. If the LLM is manipulated via prompt injection into returning an absolute URL, a path traversal string (`../../internal`), or an internal hostname, the accessor will make an HTTP request to that attacker-controlled target (Server-Side Request Forgery).

## Findings

- `clinical_trials.py:197` — `self.clinical_trial_url + trial` passed directly to `aiohttp.ClientSession.get()`

## Proposed Solution

Validate `trial` against the expected NCT ID format before constructing the URL:

```python
import re

NCT_ID_RE = re.compile(r"^NCT\d{8}$")
ALLOWED_HOSTS = {"clinicaltrials.gov"}

if not NCT_ID_RE.match(trial):
    logger.error("Invalid NCT ID rejected: %s", trial)
    return "Invalid trial identifier."

url = self.clinical_trial_url + trial
parsed = urllib.parse.urlparse(url)
if parsed.hostname not in ALLOWED_HOSTS:
    logger.error("URL host not in allowlist: %s", parsed.hostname)
    return "Trial lookup unavailable."
```

## Acceptance Criteria

- [ ] `trial` parameter validated against `^NCT\d{8}$` regex before URL construction
- [ ] Invalid NCT ID returns an error string without making any HTTP request
- [ ] Constructed URL host is validated against an allowlist (`clinicaltrials.gov`)
- [ ] URL that resolves to a non-allowlisted host is rejected before the `aiohttp` call
