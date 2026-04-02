# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import json
import logging
from collections.abc import Sequence
from time import time

from azure.storage.blob.aio import BlobServiceClient

logger = logging.getLogger(__name__)


class ClinicalNoteAccessor:
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
        self._CACHE_MAX_PATIENTS: int = 5

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
        """Read all clinical notes for a given patient ID (cached per-patient, LRU eviction)."""
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

            # LRU eviction
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
        """Filter clinical notes by note type. Fallback: read_all + filter."""
        all_notes_json = await self.read_all(patient_id)
        if not note_types:
            return [json.loads(n) if isinstance(n, str) else n for n in all_notes_json]
        type_set = {t.lower() for t in note_types}
        result = []
        for note_json in all_notes_json:
            note = json.loads(note_json) if isinstance(note_json, str) else note_json
            note_type = note.get("note_type", note.get("NoteType", "")).lower()
            if note_type in type_set:
                result.append(note)
        return result

    async def get_clinical_notes_by_keywords(
        self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]
    ) -> list[dict]:
        """Filter notes by type AND keyword. Fallback: read_all + filter."""
        notes = await self.get_clinical_notes_by_type(patient_id, note_types)
        if not keywords:
            return notes
        kw_lower = [k.lower() for k in keywords]
        return [
            n for n in notes
            if any(
                kw in n.get("text", n.get("NoteText", n.get("note_text", ""))).lower()
                for kw in kw_lower
            )
        ]

    async def get_lab_results(
        self, patient_id: str, component_name: str | None = None
    ) -> list[dict]:
        """FHIR backend does not expose structured lab results via this accessor. Returns empty list."""
        return []

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """FHIR backend does not expose structured tumor markers via this accessor. Returns empty list."""
        return []

    async def _read_blob(self, blob_name: str) -> str:
        blob = await self.container_client.download_blob(blob_name)
        blob_str = await blob.readall()
        return blob_str.decode("utf-8")

    @staticmethod
    def _parse_note_id(blob_name: str) -> str:
        return blob_name.split("/")[-1].split(".")[0]
