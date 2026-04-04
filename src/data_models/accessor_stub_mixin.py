"""Mixin providing default stub implementations for clinical note accessor methods.

Consolidates identical stub methods previously duplicated across Blob, FHIR, and
Fabric accessor classes. Subclasses override only the methods they actually support.
"""

from data_models.patient_demographics import PatientDemographics


class ClinicalNoteAccessorStubMixin:
    """Default stub implementations for accessor methods.

    Subclasses should override methods they actually support with real implementations.
    The `supported_methods` classmethod returns the set of overridden (non-stub) methods.
    """

    # Methods that subclasses can override with real data
    _STUB_METHODS = frozenset({
        "get_lab_results",
        "get_tumor_markers",
        "get_pathology_reports",
        "get_radiology_reports",
        "get_cancer_staging",
        "get_medications",
        "get_diagnoses",
        "get_patient_demographics",
    })

    @classmethod
    def supported_methods(cls) -> frozenset[str]:
        """Return methods this accessor actually implements (not stubs)."""
        supported = set()
        for method_name in cls._STUB_METHODS:
            method = getattr(cls, method_name, None)
            if method is None:
                continue
            # Check if the method is overridden from the mixin
            if getattr(method, "__qualname__", "").split(".")[0] != "ClinicalNoteAccessorStubMixin":
                supported.add(method_name)
        return frozenset(supported)

    async def get_lab_results(self, patient_id: str, component_name: str | None = None) -> list[dict]:
        """Structured lab results are not available via this accessor."""
        return []

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """Structured tumor markers are not available via this accessor."""
        return []

    async def get_pathology_reports(self, patient_id: str) -> list[dict]:
        """Dedicated pathology reports are not available via this accessor."""
        return []

    async def get_radiology_reports(self, patient_id: str) -> list[dict]:
        """Dedicated radiology reports are not available via this accessor."""
        return []

    async def get_cancer_staging(self, patient_id: str) -> list[dict]:
        """Structured cancer staging is not available via this accessor."""
        return []

    async def get_medications(self, patient_id: str, order_class: str | None = None) -> list[dict]:
        """Structured medications are not available via this accessor."""
        return []

    async def get_diagnoses(self, patient_id: str) -> list[dict]:
        """Structured diagnoses are not available via this accessor."""
        return []

    async def get_patient_demographics(self, patient_id: str) -> PatientDemographics | None:
        """Patient demographics are not available via this accessor."""
        return None
