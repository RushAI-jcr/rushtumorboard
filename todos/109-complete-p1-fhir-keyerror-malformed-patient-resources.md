---
status: pending
priority: p1
issue_id: "109"
tags: [code-review, reliability, fhir]
dependencies: []
---

# 109 — Unsafe FHIR Resource Key Access Crashes Patient Metadata Retrieval

## Problem Statement

Two methods in `fhir_clinical_note_accessor.py` perform chained dictionary and list index accesses on FHIR Patient resources without any defensive handling. A single malformed or incomplete patient record — common in real-world FHIR servers where fields like `name` or `given` may be absent, empty, or structured differently across EHR versions — causes an unhandled `KeyError` or `IndexError` that crashes the entire call. For `get_patient_id_map()`, this means a single bad record in the Patient bundle prevents ALL metadata retrieval for that FHIR server, blocking the entire patient lookup flow for every user.

## Findings

- `fhir_clinical_note_accessor.py:134` — `get_patients()` uses:
  `[entry["resource"]['name'][0]['given'][0] for entry in entries]`
  Any `entry` where `"resource"` is missing, `"name"` is absent or empty, `name[0]` lacks `"given"`, or `given` is an empty list raises `KeyError` or `IndexError`. The entire list comprehension fails, returning nothing.

- `fhir_clinical_note_accessor.py:151-154` — `get_patient_id_map()` uses the same unsafe chain inside a dict comprehension:
  `{entry["resource"]["id"]: entry["resource"]["name"][0]["given"][0] + " " + entry["resource"]["name"][0]["family"] for entry in entries}`
  A single malformed entry crashes the entire mapping. There is no skip-and-continue logic.

- FHIR R4 specification marks `Patient.name` as optional (0..*) and `HumanName.given` as optional (0..*). Real Epic FHIR exports may include anonymous or test patients without a structured name. USCDI-compliant servers may also omit `given` for patients with only a single legal name.

## Proposed Solution

Replace unsafe chained access with `.get()`-based helpers that return a sentinel for missing data and skip malformed entries with a logged warning:

```python
def _extract_patient_name(resource: dict) -> str | None:
    names = resource.get("name")
    if not names:
        return None
    first_name_obj = names[0]
    given = first_name_obj.get("given") or []
    family = first_name_obj.get("family", "")
    given_str = given[0] if given else ""
    return f"{given_str} {family}".strip() or None

# In get_patients():
result = []
for entry in entries:
    resource = entry.get("resource", {})
    name = _extract_patient_name(resource)
    if name is None:
        logger.warning("get_patients: skipping entry with missing/malformed name: id=%s", resource.get("id"))
        continue
    result.append(name)
return result

# In get_patient_id_map():
mapping = {}
for entry in entries:
    resource = entry.get("resource", {})
    patient_id = resource.get("id")
    name = _extract_patient_name(resource)
    if not patient_id or name is None:
        logger.warning("get_patient_id_map: skipping malformed entry: %s", resource.get("id"))
        continue
    mapping[patient_id] = name
return mapping
```

## Acceptance Criteria

- [ ] `get_patients()` does not raise `KeyError` or `IndexError` on any malformed FHIR Patient resource
- [ ] `get_patient_id_map()` does not raise `KeyError` or `IndexError` on any malformed FHIR Patient resource
- [ ] Malformed entries are individually skipped with a `logger.warning` identifying the entry's `id` (if available)
- [ ] Valid entries in the same bundle are still returned even when one entry is malformed
- [ ] At least one test verifies that a bundle containing one well-formed and one malformed Patient resource returns exactly one result without raising an exception
