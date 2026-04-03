# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import base64
import json
import logging
import re
from collections.abc import Sequence
from typing import Any, Callable, Coroutine

import aiohttp
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import get_bearer_token_provider

from data_models.accessor_stub_mixin import ClinicalNoteAccessorStubMixin
from utils.clinical_note_filter_utils import filter_notes_by_type, filter_notes_by_keywords

logger = logging.getLogger(__name__)

class FabricClinicalNoteAccessor(ClinicalNoteAccessorStubMixin):
    _CACHE_MAX_PATIENTS: int = 5

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
        self._read_locks: dict[str, asyncio.Lock] = {}
        self._session: aiohttp.ClientSession | None = None

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

    async def get_headers(self) -> dict[str, str]:
        """
        Returns the headers required for Fabric API requests.

        :return: A dictionary of headers.
        """
        return {
            "Authorization": f"Bearer {await self.bearer_token_provider()}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy session: created on first use, reused across requests."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the shared aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_patients(self) -> list[str]:
        """Get the list of patients."""
        target_endpoint = f"{self.api_endpoint}/functions/get_patients_by_id/invoke"
        headers = await self.get_headers()
        session = await self._get_session()
        async with session.post(target_endpoint, json={}, headers=headers) as response:
            response.raise_for_status()
            content = await response.content.read()
            data = json.loads(content.decode('utf-8'))
        return data['output']['ids']

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        """Get the clinical note URLs for a given patient ID."""
        target_endpoint = f"{self.api_endpoint}/functions/get_clinical_notes_by_patient_id/invoke"
        headers = await self.get_headers()
        session = await self._get_session()
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
        """Internal: read a single note using the provided session."""
        target_endpoint = f"{self.api_endpoint}/functions/get_clinical_note_by_patient_id/invoke"
        headers = await self.get_headers()
        async with session.post(target_endpoint, json={"noteId": note_id}, headers=headers) as response:
            response.raise_for_status()
            content = await response.content.read()
            data = json.loads(content.decode('utf-8'))
        document_reference = data["output"]
        document_reference_data = document_reference["content"][0]["attachment"]["data"]
        note_content = base64.b64decode(document_reference_data).decode("utf-8")

        try:
            note_json = json.loads(note_content)
            note_json['id'] = note_id
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Non-JSON content for Fabric note: %s — using plain text fallback", exc)
            note_json = {
                "id": note_id,
                "text": note_content,
                "date": "",
                "type": "clinical note",
            }
        return json.dumps(note_json)

    async def read(self, patient_id: str, note_id: str) -> str:
        """Read the clinical note for a given patient ID and note ID."""
        session = await self._get_session()
        return await self._read_note(note_id, session)

    async def read_all(self, patient_id: str) -> list[str]:
        """Retrieves all clinical notes for a given patient ID (cached per-patient, FIFO eviction)."""
        if patient_id in self._note_cache:
            return self._note_cache[patient_id]

        if patient_id not in self._read_locks:
            self._read_locks[patient_id] = asyncio.Lock()

        async with self._read_locks[patient_id]:
            if patient_id in self._note_cache:
                return self._note_cache[patient_id]

            metadata_list = await self.get_metadata_list(patient_id)

            notes = []
            batch_size = 10
            session = await self._get_session()
            for i in range(0, len(metadata_list), batch_size):
                batch_input = metadata_list[i:i + batch_size]
                batch = [self._read_note(note["id"], session) for note in batch_input]
                batch_results = await asyncio.gather(*batch)
                notes.extend(batch_results)

            # FIFO eviction (oldest entry removed first)
            if len(self._note_cache) >= self._CACHE_MAX_PATIENTS:
                oldest = next(iter(self._note_cache))
                del self._note_cache[oldest]
            self._note_cache[patient_id] = notes

            # Clean up the per-patient lock — cache is populated, lock is no longer needed
            self._read_locks.pop(patient_id, None)

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
            filter_notes_by_type(await self.read_all(patient_id), note_types),
            keywords,
        )

