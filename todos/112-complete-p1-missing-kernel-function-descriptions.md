---
status: pending
priority: p1
issue_id: "112"
tags: [code-review, agent-native, quality]
dependencies: []
---

# 112 — `@kernel_function` Decorators Missing `description` Arguments Degrade Tool Selection

## Problem Statement

Semantic Kernel exposes the `description` field of each `@kernel_function` decorator to the LLM as part of the tool manifest used for tool selection. Without a description, the LLM has no basis for deciding when or why to call the function — it must infer from the function name alone. For functions with generic names like `process_prompt` or `create_timeline`, this causes tool selection errors: the agent either fails to call the tool when it should, calls it at the wrong time, or calls it redundantly.

Six functions across three plugin files have bare `@kernel_function()` decorators with no `description`. Additionally, `load_patient_data` has a misleading description ("Load patient images and reports") that omits its critical side effect of setting `chat_ctx.patient_id` — the one side effect that must happen before any other tool in the plugin is called.

## Findings

Bare `@kernel_function()` (no description) in:
- `medical_research.py` — `process_prompt`
- `clinical_trials.py` — `generate_clinical_trial_search_criteria`
- `clinical_trials.py` — `search_clinical_trials`
- `clinical_trials.py` — `display_more_information_about_a_trial`
- `patient_data.py` — `create_timeline`
- `patient_data.py` — `process_prompt`

Misleading description:
- `patient_data.py:75` — `load_patient_data`: description reads "Load patient images and reports". Actual behavior: loads all note types AND sets `chat_ctx.patient_id` AND must be called before `create_timeline` and `process_prompt`. None of this is documented in the description.

## Proposed Solution

Add a `description=` string to every bare `@kernel_function()` decorator. Descriptions should:
- State what the function does in one sentence
- List any required prerequisites (e.g., "must be called after `load_patient_data`")
- Note any significant side effects

Example additions:

```python
# patient_data.py
@kernel_function(
    description=(
        "Load all clinical notes and imaging reports for the patient and set the active patient ID. "
        "MUST be called before create_timeline or process_prompt. "
        "Sets patient_id on the shared chat context as a side effect."
    )
)
async def load_patient_data(self, patient_id: str) -> str: ...

@kernel_function(
    description=(
        "Analyze loaded patient data and answer a clinical question using the patient's notes. "
        "Requires load_patient_data to have been called first."
    )
)
async def process_prompt(self, prompt: str) -> str: ...

@kernel_function(
    description=(
        "Generate a chronological timeline of the patient's clinical events from loaded notes. "
        "Requires load_patient_data to have been called first."
    )
)
async def create_timeline(self) -> str: ...
```

```python
# clinical_trials.py
@kernel_function(
    description="Generate structured search criteria (NCT filters) for ClinicalTrials.gov based on the patient's diagnosis and prior treatments."
)
async def generate_clinical_trial_search_criteria(self, ...) -> str: ...

@kernel_function(
    description="Search ClinicalTrials.gov for trials matching the patient's criteria. Call generate_clinical_trial_search_criteria first."
)
async def search_clinical_trials(self, ...) -> str: ...

@kernel_function(
    description="Retrieve and summarize detailed eligibility criteria for a specific clinical trial by NCT ID."
)
async def display_more_information_about_a_trial(self, nct_id: str) -> str: ...
```

```python
# medical_research.py
@kernel_function(
    description="Answer a clinical research question using PubMed literature and return a cited summary."
)
async def process_prompt(self, prompt: str) -> str: ...
```

## Acceptance Criteria

- [ ] All `@kernel_function` decorators across `medical_research.py`, `clinical_trials.py`, and `patient_data.py` have a non-empty `description` argument
- [ ] `load_patient_data` description explicitly documents: (1) the `patient_id` side effect on `ChatContext`, and (2) that it must be called before `create_timeline` or `process_prompt`
- [ ] `get_tumor_marker_trend` description (if bare) documents that output is raw JSON intended for PPTX rendering
- [ ] A CI check or linter rule verifies no `@kernel_function()` decorator in the codebase is missing a `description` argument
