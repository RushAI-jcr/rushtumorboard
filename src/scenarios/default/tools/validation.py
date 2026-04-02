import re

_PATIENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}$')


def validate_patient_id(patient_id: str) -> bool:
    return bool(_PATIENT_ID_RE.fullmatch(patient_id))
