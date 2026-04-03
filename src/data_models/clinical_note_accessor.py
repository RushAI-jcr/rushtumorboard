# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import logging
from collections.abc import Sequence
from time import time

from azure.storage.blob.aio import BlobServiceClient

from data_models.accessor_stub_mixin import ClinicalNoteAccessorStubMixin
from utils.clinical_note_filter_utils import filter_notes_by_type, filter_notes_by_keywords

logger = logging.getLogger(__name__)


class BlobClinicalNoteAccessor(ClinicalNoteAccessorStubMixin):
    _CACHE_MAX_PATIENTS: int = 5

    def __init__(
        self, blob_service_client: BlobServiceClient,
        container_name: str = "patient-data",
        folder_name: str = "clinical_notes"
    ):
        self.blob_service_client = blob_service_client
        self.container_name = container_name
        self.container_client = self.blob_service_client.get_container_client(self.container_name)
        self.folder_name = folder_name
        self._note_cache: dict[str, list[str]] = {}

    async def get_patients(self) -> list[str]:
        """Get the list of patients."""
        start = time()
        try:
            blob_names = [name async for name in self.container_client.list_blob_names()]
            patients = {name.split("/")[0] for name in blob_names}
            return list(patients)
        finally:
            logger.info("Get patients. Duration: %.3fs", time() - start)

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        """Get the clinical note URLs for a given patient ID."""
        start = time()
        try:
            blob_path = f"{patient_id}/{self.folder_name}/"
            blob_names = [name async for name in self.container_client.list_blob_names(name_starts_with=blob_path)]

            return [
                {
                    "id": self._parse_note_id(blob_name),
                    "type": "clinical note",
                } for blob_name in blob_names
            ]
        finally:
            logger.info("Get clinical note IDs. Duration: %.3fs", time() - start)

    async def read(self, patient_id: str, note_id: str) -> str:
        """Read the clinical note for a given patient ID and note ID."""
        start = time()
        try:
            blob_path = f"{patient_id}/{self.folder_name}/{note_id}.json"
            return await self._read_blob(blob_path)
        finally:
            logger.info("Read clinical note. Duration: %.3fs", time() - start)

    async def read_all(self, patient_id: str) -> list[str]:
        """Read all clinical notes for a given patient ID (cached per-patient, FIFO eviction)."""
        if patient_id in self._note_cache:
            return self._note_cache[patient_id]

        start = time()
        try:
            blob_path = f"{patient_id}/{self.folder_name}/"
            blob_names = [name async for name in self.container_client.list_blob_names(name_starts_with=blob_path)]
            batch_size = 10

            # Read blobs in batches
            notes = []
            for i in range(0, len(blob_names), batch_size):
                batch_input = blob_names[i:i + batch_size]
                batch = [self._read_blob(note_id) for note_id in batch_input]
                batch_results = await asyncio.gather(*batch)
                notes.extend(batch_results)

            # FIFO eviction (oldest entry removed first)
            if len(self._note_cache) >= self._CACHE_MAX_PATIENTS:
                oldest = next(iter(self._note_cache))
                del self._note_cache[oldest]
            self._note_cache[patient_id] = notes

            return notes
        finally:
            logger.info("Read all clinical notes. Duration: %.3fs", time() - start)

    async def get_clinical_notes_by_type(
        self, patient_id: str, note_types: Sequence[str]
    ) -> list[dict]:
        """Filter clinical notes by note type."""
        return filter_notes_by_type(await self.read_all(patient_id), note_types)

    async def get_clinical_notes_by_keywords(
        self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]
    ) -> list[dict]:
        """Filter notes by type AND keyword."""
        return filter_notes_by_keywords(
            filter_notes_by_type(await self.read_all(patient_id), note_types),
            keywords,
        )

    async def _read_blob(self, blob_name: str) -> str:
        blob = await self.container_client.download_blob(blob_name)
        blob_str = await blob.readall()
        return blob_str.decode("utf-8")

    @staticmethod
    def _parse_note_id(blob_name: str) -> str:
        return blob_name.split("/")[-1].split(".")[0]
