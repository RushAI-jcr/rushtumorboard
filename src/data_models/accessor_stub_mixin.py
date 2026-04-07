"""Mixin providing default stub implementations for clinical note accessor methods.

Consolidates identical stub methods previously duplicated across Blob, FHIR, and
Fabric accessor classes. Subclasses override only the methods they actually support.
"""

import logging
from collections.abc import Sequence

from data_models.patient_demographics import PatientDemographics

logger = logging.getLogger(__name__)


class ClinicalNoteAccessorStubMixin:
    """Default stub implementations for accessor methods.

    Subclasses should override methods they actually support with real implementations.
    Stub methods log a WARNING on first call so silent data gaps are visible in production.
    """

    async def get_lab_results(self, patient_id: str, component_name: str | None = None) -> list[dict]:
        """Structured lab results are not available via this accessor."""
        logger.warning("%s.get_lab_results: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_lab_results_with_notes_fallback(
        self, patient_id: str, component_name: str | None = None,
        keywords: Sequence[str] | None = None,
    ) -> list[dict]:
        """Lab results with clinical notes fallback — default delegates to get_lab_results."""
        return await self.get_lab_results(patient_id, component_name)

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """Structured tumor markers are not available via this accessor."""
        logger.warning("%s.get_tumor_markers: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_pathology_reports(self, patient_id: str) -> list[dict]:
        """Dedicated pathology reports are not available via this accessor."""
        logger.warning("%s.get_pathology_reports: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_radiology_reports(self, patient_id: str) -> list[dict]:
        """Dedicated radiology reports are not available via this accessor."""
        logger.warning("%s.get_radiology_reports: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_cancer_staging(self, patient_id: str) -> list[dict]:
        """Structured cancer staging is not available via this accessor."""
        logger.warning("%s.get_cancer_staging: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_medications(self, patient_id: str, order_class: str | None = None) -> list[dict]:
        """Structured medications are not available via this accessor."""
        logger.warning("%s.get_medications: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_diagnoses(self, patient_id: str) -> list[dict]:
        """Structured diagnoses are not available via this accessor."""
        logger.warning("%s.get_diagnoses: stub — returning empty for patient %s", type(self).__name__, patient_id)
        return []

    async def get_patient_demographics(self, patient_id: str) -> PatientDemographics | None:
        """Patient demographics are not available via this accessor."""
        logger.warning("%s.get_patient_demographics: stub — returning None for patient %s", type(self).__name__, patient_id)
        return None
