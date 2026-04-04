---
status: complete
priority: p2
issue_id: "164"
tags: [code-review, testing, cervical, gtn, synthetic-data]
dependencies: []
---

# New Synthetic Patients Not Covered by Automated Tests

## Problem Statement

`patient_gyn_cerv_001` and `patient_gyn_gtn_001` are not in the `TestSyntheticData` parametrize list and `test_disease_index_populated` doesn't assert cervical/GTN disease keys. If a CSV has a schema mismatch or the NCCN JSON files fail to load, no test catches it.

**Why:** The synthetic patients were created to validate cervical and GTN agent behavior. Without test coverage, a broken CSV column or missing guideline file would silently fail in production during an actual tumor board case.

**How to apply:** Extend the test parametrize lists and add assertions to the disease index test.

## Findings

**Source:** architecture-strategist + agent-native-reviewer

**Location:** `src/tests/test_local_agents.py`

```python
# Current (line 44–45) — only 2 patients
PATIENT_ID = "patient_gyn_001"
PATIENT_ID_2 = "patient_gyn_002"

# TestSyntheticData.test_csv_exists parametrize (line 82) — doesn't include new patients
# test_disease_index_populated (line 446–450) — only asserts endometrial_carcinoma, vaginal_cancer, vulvar_cancer
```

**Additional gap:** `test_get_tumor_markers` at line 140 asserts `ca-125` is present — this will fail for the GTN patient (whose marker is `beta-hcg`).

## Proposed Solutions

### Option A: Add constants + extend parametrize (Recommended)

```python
# Add at top of file
PATIENT_ID_3 = "patient_gyn_cerv_001"
PATIENT_ID_4 = "patient_gyn_gtn_001"

# Extend TestSyntheticData.test_csv_exists and test_caboodle_reads_all_file_types
@pytest.mark.parametrize("patient_id", [PATIENT_ID, PATIENT_ID_2, PATIENT_ID_3, PATIENT_ID_4])

# Add to test_disease_index_populated
assert "cervical_cancer" in plugin._disease_index
assert "gestational_trophoblastic_neoplasia" in plugin._disease_index
assert "hydatidiform_mole" in plugin._disease_index

# Add lookup tests
async def test_lookup_cerv1(nccn_plugin):
    result = await nccn_plugin.lookup_nccn_page(page_code="CERV-1")
    assert "CERV-1" in result

# Scope CA-125 tumor marker test to ovarian/endometrial patients only
```

- **Pros:** Matches existing test style, minimal changes
- **Effort:** Small
- **Risk:** None

### Option B: Create separate TestCervicalPatient and TestGTNPatient classes
- **Pros:** Keeps disease-specific assertions organized
- **Cons:** More boilerplate
- **Effort:** Medium

## Recommended Action

_(Leave blank — fill during triage)_

## Technical Details

- **Affected file:** `src/tests/test_local_agents.py`
- **New data directories:** `infra/patient_data/patient_gyn_cerv_001/`, `infra/patient_data/patient_gyn_gtn_001/`

## Acceptance Criteria

- [ ] Both new patients are covered by `test_csv_exists`
- [ ] `test_disease_index_populated` asserts `cervical_cancer`, `gestational_trophoblastic_neoplasia`, `hydatidiform_mole`
- [ ] CERV-1 and GTN-1 (or HM-1) lookup tests added
- [ ] CA-125 tumor marker assertion scoped to ovarian/endometrial patients
- [ ] All tests pass: `pytest src/tests/test_local_agents.py -v`

## Work Log

- 2026-04-03: Identified by architecture-strategist + agent-native-reviewer during code review

## Resources

- Test file: `src/tests/test_local_agents.py`
- New patient data: `infra/patient_data/patient_gyn_cerv_001/`, `infra/patient_data/patient_gyn_gtn_001/`
