---
status: pending
priority: p3
issue_id: "169"
tags: [code-review, security, validation]
dependencies: ["165"]
---

# Add Field-Level Validation for Demographics CSV Values

## Problem Statement

Demographics CSV values are read raw and injected into LLM prompts without sanitization. While export prompts include security preambles, a malicious/corrupted CSV with prompt injection in PatientName could be reflected directly in output. MRN should be validated as numeric, PatientName as alphabetic, DOB as date format, Sex as enum.

## Findings

- **Source**: Security Sentinel (MEDIUM)
- **Files**: `src/data_models/epic/caboodle_file_accessor.py:271-279`, `src/scenarios/default/tools/patient_data.py`

## Proposed Solutions

Add validation in `get_patient_demographics()` or after loading in `patient_data.py`. Example: MRN matches `^\d{5,10}$`, PatientName contains only letters/spaces/hyphens, DOB is a date, Sex in {Female, Male, Other, Unknown}.

## Acceptance Criteria

- [ ] MRN validated against numeric pattern
- [ ] PatientName validated against safe character set
- [ ] Invalid values logged and defaulted to safe placeholders

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | Security Sentinel flagged indirect prompt injection risk |
