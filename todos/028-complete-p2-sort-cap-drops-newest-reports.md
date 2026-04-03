---
status: pending
priority: p2
issue_id: "018"
tags: [code-review, performance, clinical-quality, radiology, pathology]
dependencies: []
---

## Problem Statement

In `MedicalReportExtractorBase._extract()`, reports are sorted ascending (oldest → newest) and then capped with `[:MAX_REPORTS]`. When a patient has more than 25 pathology or radiology reports, this silently sends the 25 **oldest** reports to the LLM and drops the most recent — which are the most clinically relevant for tumor board presentation.

```python
reports = sorted(reports, key=_report_date_key)   # oldest first
# ...
if total_available > self.MAX_REPORTS:
    reports = reports[:self.MAX_REPORTS]           # BUG: keeps 25 oldest, drops newest
```

For a patient with 5 years of follow-up imaging (common in GYN oncology), this means the most recent CT/MRI showing current disease burden is silently omitted.

## Findings

- **File:** `src/scenarios/default/tools/medical_report_extractor.py` lines 103–112
- **Reported by:** performance-oracle (P2)
- **Severity:** P2 — clinical quality impact; agents produce outdated disease assessment for long-follow-up patients

## Proposed Solutions

### Option A (Recommended): Keep newest N reports
```python
reports = sorted(reports, key=_report_date_key)   # oldest first
total_available = len(reports)
if total_available > self.MAX_REPORTS:
    logger.info(
        "Capping %s reports from %d to %d for patient %s (layer %d) — keeping most recent",
        self.report_type, total_available, self.MAX_REPORTS, patient_id, source_layer,
    )
    reports = reports[-self.MAX_REPORTS:]          # FIXED: keep newest 25
```
- **Pros:** Most recent reports (highest clinical relevance) always included; ascending order preserved for LLM readability
- **Cons:** Oldest historical context dropped (e.g., original diagnosis imaging); mitigated by OncologicHistory agent
- **Effort:** 1-line fix
- **Risk:** Low

### Option B: Keep newest N but log the date range omitted
Same as A but add log showing date range of dropped reports for operator awareness.
- **Effort:** Small
- **Risk:** None

### Option C: Keep first + last N/2 reports (bracketing)
Send the first 5 (original diagnosis context) + last 20 (recent trajectory). Most complex but preserves both endpoints.
- **Effort:** Medium
- **Risk:** Medium (changes list structure passed to LLM)

## Recommended Action

Option A — it's a one-character fix (`[:]` → `[-self.MAX_REPORTS:]`) with immediate clinical quality improvement.

## Technical Details

- **Affected file:** `src/scenarios/default/tools/medical_report_extractor.py`
- **Line:** 112 — `reports = reports[:self.MAX_REPORTS]` → `reports = reports[-self.MAX_REPORTS:]`
- **Affected agents:** Pathology (pathology_extractor), Radiology (radiology_extractor) — both inherit from MedicalReportExtractorBase

## Acceptance Criteria

- [ ] `reports[:self.MAX_REPORTS]` replaced with `reports[-self.MAX_REPORTS:]` on line 112
- [ ] Log message updated to mention "keeping most recent N"
- [ ] Verified: for a patient with 30 reports spanning 2020–2025, the 2024–2025 reports are included in LLM input

## Work Log

- 2026-04-02: Identified by performance-oracle during code review
