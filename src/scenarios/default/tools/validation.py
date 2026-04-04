import logging
import re

from data_models.patient_demographics import PatientDemographics

_PATIENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}$')

# Demographics field validation patterns
_MRN_RE = re.compile(r'^\d{5,10}$|^SYN-\d{4}$')
_PATIENT_NAME_RE = re.compile(r"^[A-Za-z\s',.\-]{1,100}$")
_DOB_RE = re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$')
_VALID_SEX = frozenset({"male", "female", "unknown", "other"})
_SEX_CANONICAL = {"male": "Male", "female": "Female", "unknown": "Unknown", "other": "Other"}


def validate_patient_id(patient_id: str) -> bool:
    return bool(_PATIENT_ID_RE.fullmatch(patient_id))


def validate_demographics(demographics: dict, log: logging.Logger) -> PatientDemographics:
    """Sanitize demographics dict: validate fields, replace invalid values with safe defaults.

    Logs warnings for invalid fields (no PHI in log messages — patient_id only via caller).
    Returns a cleaned PatientDemographics TypedDict.
    """
    result: PatientDemographics = {}

    # PatientID — pass through as-is (already validated upstream)
    if "PatientID" in demographics:
        result["PatientID"] = str(demographics["PatientID"]).strip()

    # MRN
    mrn = str(demographics.get("MRN", "")).strip()
    if mrn and _MRN_RE.fullmatch(mrn):
        result["MRN"] = mrn
    else:
        if mrn:
            log.warning("Demographics: invalid MRN format, replacing with placeholder")
        result["MRN"] = "[MRN - VERIFY]"

    # PatientName
    name = str(demographics.get("PatientName", "")).strip()
    if name and _PATIENT_NAME_RE.fullmatch(name):
        result["PatientName"] = name
    else:
        if name:
            log.warning("Demographics: invalid PatientName format, replacing with placeholder")
        result["PatientName"] = "[Name - VERIFY]"

    # DOB
    dob = str(demographics.get("DOB", "")).strip()
    if dob and _DOB_RE.fullmatch(dob):
        result["DOB"] = dob
    else:
        if dob:
            log.warning("Demographics: invalid DOB format, replacing with placeholder")
        result["DOB"] = "[DOB - VERIFY]"

    # Sex
    sex = str(demographics.get("Sex", "")).strip().lower()
    if sex in _VALID_SEX:
        result["Sex"] = _SEX_CANONICAL[sex]
    else:
        if sex:
            log.warning("Demographics: invalid Sex value, defaulting to Unknown")
        result["Sex"] = "Unknown"

    return result
