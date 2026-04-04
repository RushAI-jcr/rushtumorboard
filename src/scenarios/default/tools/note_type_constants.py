# Epic Caboodle NoteType string constants for GYN Oncology Tumor Board
#
# All values are confirmed against real Rush University Epic Clarity exports.
# Single source of truth: add new NoteTypes here and they propagate everywhere.
#
# NoteType values confirmed in real Rush Caboodle exports (2025):
#   "Progress Notes", "Consults", "ED Provider Notes", "Patient Instructions"
# NOT confirmed in real data (present in synthetic data / other Epic configs):
#   "H&P", "Operative Report", "Discharge Summary"

# --- Atomic building blocks (canonical Epic NoteType values) ---
PROGRESS_NOTE_TYPES: tuple[str, ...] = ("Progress Notes", "Progress Note")
CONSULT_NOTE_TYPES: tuple[str, ...] = ("Consults", "Consult Note", "Oncology Consultation")
HP_TYPES: tuple[str, ...] = ("H&P", "H&P (View-Only)", "History and Physical", "Interval H&P Note")
DISCHARGE_TYPES: tuple[str, ...] = ("Discharge Summary",)
OPERATIVE_TYPES: tuple[str, ...] = (
    "Operative Report", "Operative Note", "Brief Op Note",
    "Procedures", "Procedure Note", "Procedure Notes",
)
ED_NOTE_TYPES: tuple[str, ...] = (
    "ED Provider Notes", "ED Notes",
    "ED Provider Handoff Notes", "ED Procedure Note",
)
ASSESSMENT_PLAN_TYPES: tuple[str, ...] = ("Assessment & Plan Note", "AdmissionCare Note")
ONCOLOGY_TYPES: tuple[str, ...] = (
    "Chemotherapy Treatment Note", "Multidisciplinary Tumor Board",
    "Genetic Counseling", "Result Encounter Note",
)
EXTERNAL_TYPES: tuple[str, ...] = ("Unmapped External Note",)
ADDENDUM_TYPES: tuple[str, ...] = ("Addendum Note",)
TELEPHONE_TYPES: tuple[str, ...] = ("Telephone Encounter",)
PATHOLOGY_REPORT_TYPES: tuple[str, ...] = ("Surgical Pathology Final", "Pathology Consultation")

# --- Composite sets (used directly by tool classes) ---
GENERAL_CLINICAL_TYPES: tuple[str, ...] = (
    PROGRESS_NOTE_TYPES + CONSULT_NOTE_TYPES + HP_TYPES + DISCHARGE_TYPES + ED_NOTE_TYPES
)
ALL_CLINICAL_TYPES: tuple[str, ...] = (
    GENERAL_CLINICAL_TYPES + OPERATIVE_TYPES + ASSESSMENT_PLAN_TYPES
    + ONCOLOGY_TYPES + EXTERNAL_TYPES + ADDENDUM_TYPES
)
# Note: PATHOLOGY_REPORT_TYPES is intentionally excluded from ALL_CLINICAL_TYPES.
# Pathology notes are retrieved via get_pathology_reports() (Layer 1 CSV) or the
# pathology extractor's Layer 2 note types, not via the general clinical note filter.

# --- Tiered note types for data source fallback architecture ---
# NOTE: Some types (e.g. "Oncology Consultation") intentionally appear in both
# Tier A and Tier B lists. Tiers are priority-ordered, not partitions — when a
# caller combines both tiers (e.g. pretumor_board_checklist imaging fallback),
# deduplication happens at the accessor level.
#
# Tier A: Oncology-specific note types — most likely to contain structured
# oncologic data (staging, treatment plans, molecular results), especially for
# OSH transfer patients whose outside records arrive in consult notes.
ONCOLOGY_TIER_A_TYPES: tuple[str, ...] = ONCOLOGY_TYPES + ("Oncology Consultation",)

# Tier B: General clinical notes — broad clinical context from all specialties.
GENERAL_TIER_B_TYPES: tuple[str, ...] = (
    PROGRESS_NOTE_TYPES + HP_TYPES + CONSULT_NOTE_TYPES + DISCHARGE_TYPES
    + OPERATIVE_TYPES + ED_NOTE_TYPES + ADDENDUM_TYPES + TELEPHONE_TYPES
    + EXTERNAL_TYPES
)
