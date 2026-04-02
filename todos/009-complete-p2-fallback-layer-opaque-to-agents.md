---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, agent-native, architecture]
dependencies: []
---

## Problem Statement

The `source_layer` used in `MedicalReportExtractorBase._extract()` to vary the LLM preamble is never returned to the calling agent. The JSON returned to `extract_pathology_findings` / `extract_radiology_findings` contains `report_count` but no indication of whether those findings came from:
- Layer 1: a dedicated `pathology_reports.csv` (high fidelity)
- Layer 3: keyword-matched H&P and Progress Notes (low fidelity)

This matters clinically: the Pathology agent's instructions say to "state what is missing and recommend additional testing" — it cannot do that intelligently without knowing the data source quality.

Additionally, volume cap truncation is invisible to agents: when `MAX_REPORTS=25` fires, the returned JSON has no `truncated: true` flag or `available_reports: N, sent_to_llm: 25` field.

## Findings

- **File:** `src/scenarios/default/tools/medical_report_extractor.py`
- **Line:** 173 (`findings["report_count"] = len(reports)`)
- **Reported by:** agent-native-reviewer
- **Severity:** P2 — agents cannot communicate data quality; clinically significant for tumor board presentations

## Proposed Solutions

### Option A (Recommended): Add source layer metadata to returned JSON

```python
# In _extract(), after findings = json.loads(json_str):
findings["patient_id"] = patient_id
findings["report_count"] = len(reports)
findings["data_source_layer"] = source_layer
findings["data_source_description"] = {
    1: "Dedicated report CSV",
    2: "Domain-specific clinical notes (operative/procedure notes)",
    3: "Keyword-matched general clinical notes (progress notes, H&P, consults)",
}.get(source_layer, "Unknown")

# If truncation fired, add:
if len(reports) > self.MAX_REPORTS:
    findings["truncation_note"] = f"Note: {total_available} reports available; {self.MAX_REPORTS} sent to LLM due to context limits."
```

The LLM preamble already varies by layer (lines 127-141) so the LLM extraction is calibrated. This just makes that signal available to the downstream agent in its JSON response.

- **Effort:** Small
- **Risk:** None — additive fields only

## Recommended Action

Option A — two-line addition to the JSON assembly block.

## Technical Details

- **Affected file:** `src/scenarios/default/tools/medical_report_extractor.py` line 173

## Acceptance Criteria

- [ ] All responses from `_extract()` include `data_source_layer` (int 1/2/3)
- [ ] All responses include `data_source_description` (human-readable string)
- [ ] When truncation fires, response includes a truncation note
- [ ] The Pathology and Radiology agents can reference `data_source_layer` in their output

## Work Log

- 2026-04-02: Identified by agent-native-reviewer during code review
