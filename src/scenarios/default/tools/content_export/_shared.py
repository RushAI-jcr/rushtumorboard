from __future__ import annotations

# Default per-field character caps applied before LLM serialization.
# Uses the larger value when content_export and presentation_export differ.
_MAX_FIELD_CAPS: dict[str, int] = {
    "pathology_findings": 3000,
    "radiology_findings": 3000,
    "treatment_plan": 4000,
    "oncologic_history": 4000,
    "board_discussion": 3000,
    "clinical_trials": 2000,
    "tumor_markers": 2000,
}


def prepare_export_data(
    kwargs: dict,
    demographics: dict | None,
    caps: dict | None = None,
) -> dict:
    """Build the common ``all_data`` dict used by both export plugins.

    Parameters
    ----------
    kwargs:
        Raw keyword arguments forwarded from the export tool function.
        Must contain at least the common fields (patient_id, patient_age, etc.).
        Extra keys (e.g. medical_history, ct_scan_findings) are preserved as-is.
    demographics:
        Patient demographics dict (MRN, name, DOB, sex) or None.
    caps:
        Optional per-field character-limit overrides.  Merged on top of
        ``_MAX_FIELD_CAPS`` so either consumer can customize individual caps.
    """
    all_data = dict(kwargs)

    if demographics:
        all_data["patient_demographics"] = demographics

    effective_caps = dict(_MAX_FIELD_CAPS)
    if caps:
        effective_caps.update(caps)

    for field, limit in effective_caps.items():
        if field in all_data:
            all_data[field] = str(all_data.get(field) or "")[:limit]

    return all_data
