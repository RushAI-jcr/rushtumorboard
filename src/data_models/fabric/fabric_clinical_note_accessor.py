# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import logging
from collections.abc import Sequence
from typing import Any, Callable, Coroutine
import json
import base64
from datetime import date, timedelta

import re
import aiohttp
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import get_bearer_token_provider

from data_models.clinical_note_filter_utils import filter_notes_by_type, filter_notes_by_keywords

logger = logging.getLogger(__name__)

class FabricClinicalNoteAccessor:
    def __init__(
        self,
        fabric_user_data_function_endpoint: str,
        bearer_token_provider: Callable[[], Coroutine[Any, Any, str]],
    ):
        self.fabric_user_data_function_endpoint = fabric_user_data_function_endpoint
        parsed = self.__parse_fabric_endpoint(fabric_user_data_function_endpoint)
        if parsed is None:
            raise ValueError(
                f"Could not parse Fabric endpoint URL. Expected format: "
                f"https://api.fabric.microsoft.com/v1/workspaces/{{workspace_id}}/userDataFunctions/{{data_function_id}} "
                f"or https://msit.powerbi.com/groups/{{workspace_id}}/userdatafunctions/{{data_function_id}}. "
                f"Got: {fabric_user_data_function_endpoint}"
            )
        workspace_id, data_function_id = parsed
        self.api_endpoint = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/userDataFunctions/{data_function_id}"
        self.bearer_token_provider = bearer_token_provider
        self._note_cache: dict[str, list[str]] = {}
        self._CACHE_MAX_PATIENTS: int = 5

    def __parse_fabric_endpoint(self, url: str) -> tuple[str, str] | None:
        """
        Parses a Fabric API URL to extract the workspace_id and data_function_id.

        Supports both the following patterns:
        https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/userDataFunctions/{data_function_id}
        and
        https://msit.powerbi.com/groups/{workspace_id}/userdatafunctions/{data_function_id}

        :param url: The Fabric API URL.
        :return: Tuple of (workspace_id, data_function_id) if found, else None.
        """
        # Try both possible patterns (case-insensitive for 'userdatafunctions')
        patterns = [
            r"/workspaces/([^/]+)/userDataFunctions/([^/]+)",
            r"/groups/([^/]+)/userdatafunctions/([^/]+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                workspace_id, data_function_id = match.groups()
                return workspace_id, data_function_id
        return None

    @staticmethod
    def from_credential(fabric_user_data_function_endpoint: str, credential: AsyncTokenCredential) -> 'FabricClinicalNoteAccessor':
        """ Creates an instance of FabricClinicalNoteAccessor using Azure credential."""
        token_provider = get_bearer_token_provider(credential, "https://analysis.windows.net/powerbi/api")
        return FabricClinicalNoteAccessor(fabric_user_data_function_endpoint, token_provider)

    async def get_headers(self) -> dict:
        """
        Returns the headers required for Fabric API requests.

        :return: A dictionary of headers.
        """
        return {
            "Authorization": f"Bearer {await self.bearer_token_provider()}",
            "Content-Type": "application/json",
        }

    async def get_patients(self) -> list[str]:
        """Get the list of patients."""
        target_endpoint = f"{self.api_endpoint}/functions/get_patients_by_id/invoke"
        headers = await self.get_headers()
        async with aiohttp.ClientSession() as session:
            async with session.post(target_endpoint, json={}, headers=headers) as response:
                response.raise_for_status()
                content = await response.content.read()
                data = json.loads(content.decode('utf-8'))
        return data['output']['ids']

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        """Get the clinical note URLs for a given patient ID."""
        target_endpoint = f"{self.api_endpoint}/functions/get_clinical_notes_by_patient_id/invoke"
        headers = await self.get_headers()
        async with aiohttp.ClientSession() as session:
            async with session.post(target_endpoint, json={"patientId": patient_id}, headers=headers) as response:
                response.raise_for_status()
                content = await response.content.read()
                data = json.loads(content.decode('utf-8'))
        document_reference_ids = data['output']

        return [
            {
                "id": doc_ref_id,
                "type": "clinical note",
            } for doc_ref_id in document_reference_ids
        ]

    async def _read_note(self, note_id: str, session: aiohttp.ClientSession) -> str:
        """Internal: read a single note using the provided session (avoids per-request session overhead)."""
        target_endpoint = f"{self.api_endpoint}/functions/get_clinical_note_by_patient_id/invoke"
        headers = await self.get_headers()
        async with session.post(target_endpoint, json={"noteId": note_id}, headers=headers) as response:
            response.raise_for_status()
            content = await response.content.read()
            data = json.loads(content.decode('utf-8'))
        document_reference = data["output"]
        document_reference_data = document_reference["content"][0]["attachment"]["data"]
        note_content = base64.b64decode(document_reference_data).decode("utf-8")

        note_json = {}
        try:
            note_json = json.loads(note_content)
            note_json['id'] = note_id
        except json.JSONDecodeError as e:
            logger.warning("Non-JSON content for note %s: %s — using plain text fallback", note_id, e)
            if note_content:
                target_date = date.today() - timedelta(days=30)
                note_json = {
                    "id": note_id,
                    "text": note_content,
                    "date": target_date.isoformat(),
                    "type": "clinical note",
                }
        return json.dumps(note_json)

    async def read(self, patient_id: str, note_id: str) -> str:
        """Read the clinical note for a given patient ID and note ID."""
        async with aiohttp.ClientSession() as session:
            return await self._read_note(note_id, session)

    async def read_all(self, patient_id: str) -> list[str]:
        """Retrieves all clinical notes for a given patient ID (cached per-patient, LRU eviction)."""
        if patient_id in self._note_cache:
            return self._note_cache[patient_id]

        metadata_list = await self.get_metadata_list(patient_id)

        notes = []
        batch_size = 10
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(metadata_list), batch_size):
                batch_input = metadata_list[i:i + batch_size]
                batch = [self._read_note(note["id"], session) for note in batch_input]
                batch_results = await asyncio.gather(*batch)
                notes.extend(batch_results)

        # LRU eviction
        if len(self._note_cache) >= self._CACHE_MAX_PATIENTS:
            oldest = next(iter(self._note_cache))
            del self._note_cache[oldest]
        self._note_cache[patient_id] = notes

        return notes

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
            await self.get_clinical_notes_by_type(patient_id, note_types), keywords
        )

    async def get_lab_results(
        self, patient_id: str, component_name: str | None = None
    ) -> list[dict]:
        """Fabric backend does not expose structured lab results via this accessor. Returns empty list."""
        return []

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """Fabric backend does not expose structured tumor markers via this accessor. Returns empty list."""
        return []

    async def get_pathology_reports(self, patient_id: str) -> list[dict]:
        """Fabric backend does not expose dedicated pathology reports. Returns empty list."""
        return []

    async def get_radiology_reports(self, patient_id: str) -> list[dict]:
        """Fabric backend does not expose dedicated radiology reports. Returns empty list."""
        return []

    async def get_cancer_staging(self, patient_id: str) -> list[dict]:
        """Fabric backend does not expose structured cancer staging. Returns empty list."""
        return []

    async def get_medications(
        self, patient_id: str, order_class: str | None = None
    ) -> list[dict]:
        """Fabric backend does not expose structured medications via this accessor. Returns empty list."""
        return []

    async def get_diagnoses(self, patient_id: str) -> list[dict]:
        """Fabric backend does not expose structured diagnoses via this accessor. Returns empty list."""
        return []