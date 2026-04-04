## Summary
<!-- 1-3 bullet points describing what this PR does and why -->
-

## Type
<!-- Check one -->
- [ ] Bug fix
- [ ] Feature / enhancement
- [ ] Refactor (no functional change)
- [ ] Agent tool or prompt change
- [ ] Infrastructure / deployment
- [ ] Documentation

## PHI / Security Checklist
<!-- All PRs must pass this checklist -->
- [ ] No patient data, GUIDs, or MRNs in code or comments
- [ ] No PHI logged at INFO level or above (DEBUG only, with metadata not content)
- [ ] No new secrets or credentials hardcoded
- [ ] Pre-commit hook passes (PHI GUID scan)

## Testing
<!-- How was this tested? -->
- [ ] `python3 -m pytest tests/test_local_agents.py -v` passes
- [ ] Tested with synthetic patient (`patient_gyn_001` or `patient_gyn_002`)
- [ ] Tested with real patient data (specify count: ___)
- [ ] `scripts/run_batch_e2e.py` batch run (if agent logic changed)
- [ ] N/A (docs, infra, or config only)

## Agent Impact
<!-- If this PR changes agent behavior, which agents are affected? -->
- [ ] Orchestrator (turn routing, termination)
- [ ] Data extraction agents (PatientHistory, Pathology, Radiology, OncologicHistory)
- [ ] Synthesis agents (PatientStatus, ClinicalGuidelines, ClinicalTrials, MedicalResearch)
- [ ] ReportCreation (Word doc, PPTX)
- [ ] No agent impact

## Notes
<!-- Anything else reviewers should know? Context, trade-offs, follow-up work. -->
