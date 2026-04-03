---
status: pending
priority: p1
issue_id: "113"
tags: [code-review, reliability, python]
dependencies: []
---

# 113 — `ClinicalTrialsPlugin.__init__` Uses Hard `os.environ[]` Access, Crashes on Missing Env Vars

## Problem Statement

`ClinicalTrialsPlugin.__init__` in `clinical_trials.py:83` accesses `os.environ["AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL"]` and `os.environ["AZURE_OPENAI_REASONING_MODEL_ENDPOINT"]` using the `[]` operator. If either variable is absent, Python raises `KeyError` with the variable name as the error message. This is a cryptic failure mode: the error surfaces wherever `ClinicalTrialsPlugin` is first instantiated (typically during app startup or group chat assembly), produces a traceback that does not mention the class name or what configuration is needed, and is particularly disruptive in development environments that only configure the primary model.

The same variables are consumed in `medical_research.py` using `.get(...)` with a fallback — inconsistent behavior for the same configuration concern. In a CI or dev environment where only the primary deployment is configured, `ClinicalTrialsPlugin` silently fails to instantiate while `MedicalResearchPlugin` loads fine, creating a confusing asymmetry.

## Findings

- `clinical_trials.py:83-87` — `os.environ["AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL"]` and `os.environ["AZURE_OPENAI_REASONING_MODEL_ENDPOINT"]` using hard key access. `KeyError` propagates at plugin instantiation time with no contextual error message.
- `medical_research.py` — same variables accessed with `.get(..., fallback_value)` pattern. The inconsistency means the two plugins behave differently under identical misconfiguration.
- There is no startup validation step that checks for required configuration and reports all missing variables at once (fail-fast with a clear summary).

## Proposed Solution

**Option A — Raise a clear `ValueError` at instantiation** (preferred for required variables):

```python
def __init__(self, ...):
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL")
    endpoint = os.environ.get("AZURE_OPENAI_REASONING_MODEL_ENDPOINT")

    if not deployment:
        raise ValueError(
            "ClinicalTrialsPlugin requires AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL "
            "to be set. Set it to the Azure OpenAI reasoning model deployment name."
        )
    if not endpoint:
        raise ValueError(
            "ClinicalTrialsPlugin requires AZURE_OPENAI_REASONING_MODEL_ENDPOINT "
            "to be set. Set it to the Azure OpenAI reasoning model endpoint URL."
        )

    self._reasoning_deployment = deployment
    self._reasoning_endpoint = endpoint
```

This converts the cryptic `KeyError: 'AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL'` into an explicit `ValueError` with actionable text.

**Option B — Fall back to primary model** (for non-blocking dev ergonomics):

```python
self._reasoning_deployment = (
    os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL")
    or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")  # primary fallback
)
```

Log a warning if the fallback is used. This matches the `medical_research.py` pattern and allows dev environments without the reasoning model to run (potentially with degraded trial evaluation quality).

**Recommended:** Apply Option A for production correctness. Add Option B as a dev convenience behind an explicit `ALLOW_REASONING_MODEL_FALLBACK=true` env var, so production deployments are never silently degraded.

Regardless of approach, align `clinical_trials.py` with `medical_research.py` so both plugins handle missing configuration identically.

## Acceptance Criteria

- [ ] A missing `AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL` raises `ValueError` with a clear, actionable message (not `KeyError`)
- [ ] A missing `AZURE_OPENAI_REASONING_MODEL_ENDPOINT` raises `ValueError` with a clear, actionable message (not `KeyError`)
- [ ] The error is raised at plugin instantiation time (startup), not at the first call to a function that uses the variable
- [ ] `clinical_trials.py` and `medical_research.py` handle missing reasoning model configuration with the same strategy
- [ ] A test verifies that instantiating `ClinicalTrialsPlugin` without the required env vars raises `ValueError` (not `KeyError`)
