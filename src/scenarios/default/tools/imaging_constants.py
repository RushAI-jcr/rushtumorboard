# Imaging-related constants for GYN Oncology Tumor Board
#
# Single source of truth for OSH hospital names and Rush affiliate identifiers.
# Referenced by radiology_extractor.py, agents.yaml, content_export.py,
# presentation_export.py, and oncologic_history_extractor.py.
#
# When adding a new outside hospital or Rush affiliate, update ONLY this file —
# Python files import these constants; YAML/prompt files reference this module
# in comments.

# Known outside hospitals seen in Rush GYN oncology referrals.
# Used in LLM system prompts (rule 13) to guide OSH tagging.
OSH_HOSPITAL_NAMES: frozenset[str] = frozenset({
    "riverside",
    "lutheran",
    "good samaritan",
    "gsh",       # Good Samaritan Hospital abbreviation
    "edwards",
})

# Rush system affiliates — imaging from these should NOT be tagged as OSH.
RUSH_AFFILIATES: frozenset[str] = frozenset({
    "rush copley",
    "copley",
})
