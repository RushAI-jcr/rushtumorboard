from typing import TypedDict


class PatientDemographics(TypedDict, total=False):
    """Patient demographics from Epic Caboodle CSV or agent extraction.

    PascalCase keys match CSV column headers directly.
    All fields optional (total=False) since some CSVs may lack columns.
    """
    PatientID: str
    MRN: str
    PatientName: str
    DOB: str
    Sex: str
