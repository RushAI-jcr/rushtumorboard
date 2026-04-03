# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import base64
import json
import logging
import urllib.parse
from collections.abc import Sequence
from typing import Any, Callable, Coroutine

import aiohttp
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import get_bearer_token_provider

from data_models.accessor_stub_mixin import ClinicalNoteAccessorStubMixin
from utils.clinical_note_filter_utils import filter_notes_by_type, filter_notes_by_keywords

logger = logging.getLogger(__name__)


class FhirClinicalNoteAccessor(ClinicalNoteAccessorStubMixin):
    _CACHE_MAX_PATIENTS: int = 5

    @staticmethod
    def from_credential(fhir_url: str, credential: AsyncTokenCredential) -> 'FhirClinicalNoteAccessor':
        """ Creates an instance of FhirClinicalNoteAccessor using Azure credential."""
        token_provider = get_bearer_token_provider(credential, f"{fhir_url}/.default")
        return FhirClinicalNoteAccessor(fhir_url, token_provider)

    @staticmethod
    def from_client_secret(tenant_id: str, client_id: str, client_secret: str, fhir_url: str) -> 'FhirClinicalNoteAccessor':
        """ Creates an instance of FhirClinicalNoteAccessor using client secret."""
        async def bearer_token_provider() -> str:
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "grant_type": "client_credentials",
                "resource": fhir_url,
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": f"{fhir_url}/.default"
            }
            async with aiohttp.request('POST', token_url, data=data, headers=headers) as resp:
                resp.raise_for_status()
                json_response = await resp.json()
                return json_response["access_token"]

        return FhirClinicalNoteAccessor(fhir_url, bearer_token_provider)

    def __init__(self, fhir_url: str, bearer_token_provider: Callable[[], Coroutine[Any, Any, str]]):
        """
        Initializes the FhirClinicalNoteAccessor.

        :param fhir_url: The base URL of the FHIR server.
        :param bearer_token_provider: Async callable that returns a bearer token string.
        """
        if not fhir_url:
            raise ValueError("FHIR URL is required.")
        if not bearer_token_provider:
            raise ValueError("bearer_token_provider is required.")

        self.fhir_url = fhir_url
        self.bearer_token_provider = bearer_token_provider
        self._note_cache: dict[str, list[str]] = {}
        self._read_locks: dict[str, asyncio.Lock] = {}
        self._patient_id_map_cache: dict[str, str] | None = None
        self._patient_id_map_lock: asyncio.Lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._session_lock: asyncio.Lock = asyncio.Lock()

    async def get_headers(self) -> dict[str, str]:
        """
        Returns the headers required for FHIR API requests.

        :return: A dictionary of headers.
        """
        return {
            "Authorization": f"Bearer {await self.bearer_token_provider()}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_continuation_token(links):
        for link in links:
            if "relation" in link and link["relation"] == "next":
                return link["url"].split("?", 1)[-1]
        return None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return shared aiohttp.ClientSession, creating it once under a lock."""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_all_entries(
        self,
        base_url: str,
        result_count_limit: int = 100,
        extract_entries=lambda r: r.get("entry", []),
        extract_continuation_token=lambda r: FhirClinicalNoteAccessor.get_continuation_token(r.get("link", []))
    ) -> list[dict]:
        """
        Generic function to fetch all entries from a paginated FHIR resource endpoint.
        :param base_url: The initial FHIR resource URL (e.g., f"{fhir_url}/Patient").
        :param result_count_limit: Maximum number of entries to fetch.
        :param extract_entries: Function to extract entries from the response JSON.
        :param extract_continuation_token: Function to extract continuation token from the response JSON.
        :return: List of resource entries.
        """
        entries = []
        url = base_url
        parsed_url = urllib.parse.urlparse(url)
        session = await self._get_session()
        while url and len(entries) < result_count_limit:
            logger.debug(f"Fetching from URL: {url}")
            async with session.get(url, headers=await self.get_headers()) as response:
                response.raise_for_status()
                response_json = await response.json()

            new_entries = extract_entries(response_json)
            entries.extend(new_entries)
            if len(entries) >= result_count_limit:
                break
            token = extract_continuation_token(response_json)
            if token:
                # Append or replace query string with continuation token
                url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{token}"
            else:
                url = None
        return entries[:result_count_limit]

    @staticmethod
    def _extract_patient_name(resource: dict) -> str | None:
        """Safely extract a display name from a FHIR Patient resource dict."""
        names = resource.get("name")
        if not names:
            return None
        first_name_obj = names[0] if isinstance(names, list) else {}
        given = first_name_obj.get("given") or []
        family = first_name_obj.get("family", "")
        given_str = given[0] if given else ""
        full = f"{given_str} {family}".strip()
        return full or None

    async def get_patients(self) -> list[str]:
        """
        Retrieves a list of patient IDs from the FHIR server.

        :return: A list of patient IDs.
        """
        entries = await self.fetch_all_entries(
            base_url=f"{self.fhir_url}/Patient",
            result_count_limit=100
        )
        result = []
        for entry in entries:
            resource = entry.get("resource", {})
            name = self._extract_patient_name(resource)
            if name is None:
                logger.warning(
                    "get_patients: skipping entry with missing/malformed name: id=%s",
                    resource.get("id"),
                )
                continue
            result.append(name)
        return result

    async def get_patient_id_map(self) -> dict[str, str]:
        """
        Retrieves a mapping of patient display names to FHIR resource IDs (cached).

        :return: Dict of {display_name: fhir_resource_id}.
        """
        if self._patient_id_map_cache is not None:
            return self._patient_id_map_cache
        async with self._patient_id_map_lock:
            if self._patient_id_map_cache is not None:
                return self._patient_id_map_cache
            entries = await self.fetch_all_entries(
                base_url=f"{self.fhir_url}/Patient",
                result_count_limit=100
            )
            mapping: dict[str, str] = {}
            for entry in entries:
                resource = entry.get("resource", {})
                patient_id = resource.get("id")
                name = self._extract_patient_name(resource)
                if not patient_id or name is None:
                    logger.warning(
                        "get_patient_id_map: skipping malformed entry: id=%s",
                        resource.get("id"),
                    )
                    continue
                mapping[name] = patient_id
            self._patient_id_map_cache = mapping
        return self._patient_id_map_cache

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        """
        Retrieves metadata for clinical notes associated with a given patient ID.
        :param patient_id: The ID of the patient.
        :return: A list of metadata dictionaries for clinical notes.
        """
        patient_id_map = await self.get_patient_id_map()
        if patient_id in patient_id_map:
            patient_id = patient_id_map[patient_id]

        document_references = await self.fetch_all_entries(
            base_url=f"{self.fhir_url}/DocumentReference?subject=Patient/{patient_id}&_elements=subject,id",
            result_count_limit=100
        )
        entries = []
        for document_reference in document_references:
            if "resource" not in document_reference:
                continue
            if "subject" not in document_reference["resource"]:
                continue
            if "reference" not in document_reference["resource"]["subject"]:
                continue
            if patient_id not in document_reference["resource"]["subject"]["reference"]:
                continue
            entries.append({
                "id": document_reference["resource"]["id"],
                "type": document_reference["resource"]["type"]["text"] if "type" in document_reference["resource"] else "clinical note",
            })
        return entries

    async def _read_note(self, note_id: str, session: aiohttp.ClientSession) -> str:
        """Internal: read a single note using the provided session (avoids per-request session overhead)."""
        url = f"{self.fhir_url}/DocumentReference/{note_id}"
        headers = await self.get_headers()
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            document_reference = await response.json()
        note_content_b64 = document_reference["content"][0]["attachment"]["data"]
        raw_text = base64.b64decode(note_content_b64).decode("utf-8")
        try:
            note_json = json.loads(raw_text)
            note_json['id'] = note_id
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Non-JSON content for FHIR note: %s — using plain text fallback", exc)
            note_json = {
                "id": note_id,
                "text": raw_text,
                "date": "",
                "type": "clinical note",
            }
        return json.dumps(note_json)

    async def read(self, patient_id: str, note_id: str) -> str:
        """Retrieves the content of a clinical note for a given patient ID and note ID."""
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
            async with aiohttp.ClientSession() as session:
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

