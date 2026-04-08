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
from data_models.patient_demographics import PatientDemographics
from utils.clinical_note_filter_utils import filter_notes_by_type, filter_notes_by_keywords

logger = logging.getLogger(__name__)


class FabricClinicalNoteAccessor(ClinicalNoteAccessorStubMixin):
    _CACHE_MAX_PATIENTS: int = 5

    # Known GYN oncology genes — mirrors CaboodleFileAccessor._GYN_ONCOLOGY_GENES
    _GYN_ONCOLOGY_GENES: frozenset[str] = frozenset({
        "BRCA1", "BRCA2", "MLH1", "MSH2", "MSH6", "PMS2", "EPCAM",
        "RAD51C", "RAD51D", "BRIP1", "PALB2", "ATM", "CHEK2",
        "STK11", "PTEN", "TP53", "MUTYH", "RAD50",
        "POLE",
        "ERBB2", "HER2", "NTRK1", "NTRK2", "NTRK3",
        "PIK3CA", "KRAS", "BRAF", "FGFR2", "FGFR3",
        "CCNE1", "CDK4", "CDK6",
        "ARID1A", "CTNNB1", "FBXW7", "PPP2R1A", "RB1",
        "NF1", "CDKN2A", "CDKN2B", "APC",
        "CD274",
        "RAD51B", "FANCA", "FANCC",
    })

    # Tumor marker component names for filtering lab results
    _TUMOR_MARKER_NAMES: frozenset[str] = frozenset([
        "ca-125", "ca125", "ca 125", "he4", "he 4",
        "hcg", "beta-hcg", "beta hcg", "quant b-hcg",
        "cea", "afp", "alpha fetoprotein", "ldh",
        "scc", "scc ag", "squamous cell carcinoma antigen",
        "inhibin",
    ])

    # Map Fabric UDF function names to structured data types.
    # As Rush deploys new UDFs, add entries here — the accessor will
    # automatically call them instead of falling back to stubs.
    _STRUCTURED_DATA_UDFS: dict[str, str] = {
        "pathology_reports": "get_pathology_reports_by_patient_id",
        "radiology_reports": "get_radiology_reports_by_patient_id",
        "lab_results": "get_lab_results_by_patient_id",
        "cancer_staging": "get_cancer_staging_by_patient_id",
        "medications": "get_medications_by_patient_id",
        "diagnoses": "get_diagnoses_by_patient_id",
        "variant_details": "get_variant_details_by_patient_id",
        "variant_interpretation": "get_variant_interpretation_by_patient_id",
        "patient_demographics": "get_patient_demographics_by_patient_id",
    }

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
        self._session_lock = asyncio.Lock()
        # Cache for structured data queries (per patient + data type)
        self._structured_cache: dict[tuple[str, str], list[dict]] = {}
        # Track which UDFs are known to be unavailable (404) to avoid repeated calls
        self._unavailable_udfs: set[str] = set()

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
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
            return self._session

    async def close(self) -> None:
        """Close the shared aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    # --- Generic UDF caller for structured data ---

    async def _call_udf(self, function_name: str, payload: dict) -> dict | None:
        """Call a Fabric User Data Function and return the parsed response.

        Returns None if the UDF is not deployed (404) or returns an error.
        Caches 404s so we don't repeatedly call missing endpoints.
        """
        if function_name in self._unavailable_udfs:
            return None

        target_endpoint = f"{self.api_endpoint}/functions/{function_name}/invoke"
        headers = await self.get_headers()
        session = await self._get_session()
        try:
            async with session.post(target_endpoint, json=payload, headers=headers) as response:
                if response.status == 404:
                    self._unavailable_udfs.add(function_name)
                    logger.info("Fabric UDF %s not deployed — using stub fallback", function_name)
                    return None
                response.raise_for_status()
                content = await response.content.read()
                return json.loads(content.decode("utf-8"))
        except aiohttp.ClientError as exc:
            logger.warning("Fabric UDF %s call failed: %s — using stub fallback", function_name, exc)
            return None

    async def _get_structured_data(self, patient_id: str, data_type: str) -> list[dict]:
        """Fetch structured data rows from a Fabric UDF.

        Returns cached results if available. Falls back to empty list if
        the UDF is not deployed (the stub mixin's warning is suppressed since
        we handle the fallback here).
        """
        cache_key = (patient_id, data_type)
        if cache_key in self._structured_cache:
            return self._structured_cache[cache_key]

        udf_name = self._STRUCTURED_DATA_UDFS.get(data_type)
        if udf_name is None:
            return []

        data = await self._call_udf(udf_name, {"patientId": patient_id})
        if data is None:
            return []

        rows = data.get("output", data.get("rows", []))
        if not isinstance(rows, list):
            rows = []

        # FIFO eviction for structured cache
        if len(self._structured_cache) >= self._CACHE_MAX_PATIENTS * 10:
            oldest = next(iter(self._structured_cache))
            del self._structured_cache[oldest]
        self._structured_cache[cache_key] = rows
        return rows

    # --- Structured data accessors (override stubs) ---

    async def get_pathology_reports(self, patient_id: str) -> list[dict]:
        """Get pathology reports from Fabric UDF."""
        rows = await self._get_structured_data(patient_id, "pathology_reports")
        if rows:
            return rows
        return await super().get_pathology_reports(patient_id)

    async def get_radiology_reports(self, patient_id: str) -> list[dict]:
        """Get radiology reports from Fabric UDF."""
        rows = await self._get_structured_data(patient_id, "radiology_reports")
        if rows:
            return rows
        return await super().get_radiology_reports(patient_id)

    async def get_lab_results(self, patient_id: str, component_name: str | None = None) -> list[dict]:
        """Get lab results from Fabric UDF, optionally filtered by component name."""
        labs = await self._get_structured_data(patient_id, "lab_results")
        if not labs:
            return await super().get_lab_results(patient_id, component_name)
        if component_name:
            labs = [
                lab for lab in labs
                if component_name.lower() in lab.get("ComponentName", lab.get("component_name", "")).lower()
            ]
        return labs

    async def get_lab_results_with_notes_fallback(
        self, patient_id: str, component_name: str | None = None,
        keywords: Sequence[str] | None = None,
    ) -> list[dict]:
        """Lab results with clinical notes fallback."""
        labs = await self.get_lab_results(patient_id, component_name)
        if labs:
            return labs

        # Fallback: search clinical notes for lab values
        search_keywords = list(keywords) if keywords else []
        if component_name and component_name.lower() not in [k.lower() for k in search_keywords]:
            search_keywords.insert(0, component_name)
        if not search_keywords:
            return []

        lab_note_types = [
            "Progress Notes", "Progress Note", "H&P", "History and Physical",
            "Oncology Consultation", "Consults", "Discharge Summary",
        ]
        notes = await self.get_clinical_notes_by_keywords(patient_id, lab_note_types, search_keywords)
        if not notes:
            return []

        return [
            {
                "ComponentName": component_name or ", ".join(search_keywords[:3]),
                "OrderDate": n.get("EntryDate", n.get("date", "")),
                "ResultValue": "",
                "source": "clinical_notes",
                "NoteType": n.get("NoteType", n.get("note_type", "")),
                "NoteText": n.get("NoteText", n.get("note_text", n.get("text", "")))[:2000],
            }
            for n in notes[:20]
        ]

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """Get tumor marker results from structured labs."""
        labs = await self._get_structured_data(patient_id, "lab_results")
        if not labs:
            return await super().get_tumor_markers(patient_id)
        return [
            lab for lab in labs
            if any(
                marker in lab.get("ComponentName", lab.get("component_name", "")).lower()
                for marker in self._TUMOR_MARKER_NAMES
            )
        ]

    async def get_cancer_staging(self, patient_id: str) -> list[dict]:
        """Get cancer staging records from Fabric UDF."""
        rows = await self._get_structured_data(patient_id, "cancer_staging")
        if rows:
            return rows
        return await super().get_cancer_staging(patient_id)

    async def get_medications(self, patient_id: str, order_class: str | None = None) -> list[dict]:
        """Get medications from Fabric UDF, optionally filtered by order class."""
        meds = await self._get_structured_data(patient_id, "medications")
        if not meds:
            return await super().get_medications(patient_id, order_class)
        if order_class:
            meds = [
                med for med in meds
                if order_class.lower() in med.get("OrderClass", med.get("order_class", "")).lower()
            ]
        return meds

    async def get_diagnoses(self, patient_id: str) -> list[dict]:
        """Get diagnoses from Fabric UDF."""
        rows = await self._get_structured_data(patient_id, "diagnoses")
        if rows:
            return rows
        return await super().get_diagnoses(patient_id)

    async def get_variant_details(self, patient_id: str, gene: str | None = None) -> list[dict]:
        """Get genomic variant details from Fabric UDF."""
        variants = await self._get_structured_data(patient_id, "variant_details")
        if not variants:
            return await super().get_variant_details(patient_id, gene)
        if gene:
            gene_lower = gene.lower()
            variants = [
                v for v in variants
                if gene_lower in v.get("GENE", v.get("gene", "")).lower()
            ]
        return variants

    async def get_variant_interpretation(self, patient_id: str) -> list[dict]:
        """Get variant interpretation narratives from Fabric UDF."""
        rows = await self._get_structured_data(patient_id, "variant_interpretation")
        if rows:
            return rows
        return await super().get_variant_interpretation(patient_id)

    async def get_molecular_data(self, patient_id: str) -> dict:
        """Get combined molecular/genomic data with actionable variant filtering.

        Mirrors CaboodleFileAccessor.get_molecular_data logic: filters for germline
        variants, known GYN oncology genes, variants with interpretations, and LOF.
        """
        details, interps = await asyncio.gather(
            self.get_variant_details(patient_id),
            self.get_variant_interpretation(patient_id),
        )

        if not details and not interps:
            return await super().get_molecular_data(patient_id)

        # Build interpretation lookup
        interp_map: dict[str, str] = {}
        for row in interps:
            vid = row.get("VARIANT_ID", row.get("variant_id", ""))
            text = row.get("CONCATENATED_TEXT", row.get("concatenated_text", ""))
            if vid and text:
                interp_map[str(vid)] = text

        interpreted_vids = set(interp_map.keys())

        # Filter actionable variants
        actionable = []
        seen_keys: set[str] = set()
        for v in details:
            gene = v.get("GENE", v.get("gene", ""))
            source = v.get("GENOMIC_SOURCE", v.get("genomic_source", "")).lower()
            consequence = v.get("MOLECULAR_CONSEQUENCE", v.get("molecular_consequence", "")).lower()
            vid = str(v.get("VARIANT_ID", v.get("variant_id", "")))

            is_germline = source == "germline"
            is_oncology_gene = gene.upper() in self._GYN_ONCOLOGY_GENES
            has_interpretation = vid in interpreted_vids
            is_lof = consequence in ("nonsense", "frameshift variant", "splice donor variant", "splice acceptor variant")

            if not (is_germline or is_oncology_gene or has_interpretation or is_lof):
                continue

            change = v.get("AMINO_ACID_CHANGE", v.get("amino_acid_change", ""))
            dedup_key = f"{gene}|{change or v.get('DNA_CHANGE', v.get('dna_change', ''))}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            interp_text = interp_map.get(vid, "")
            actionable.append({
                "gene": gene,
                "change": change or v.get("DNA_CHANGE", v.get("dna_change", "")),
                "source": v.get("GENOMIC_SOURCE", v.get("genomic_source", "")),
                "assessment": v.get("ASSESSMENT", v.get("assessment", "")),
                "consequence": v.get("MOLECULAR_CONSEQUENCE", v.get("molecular_consequence", "")),
                "interpretation": interp_text[:500] if interp_text else "",
            })

        return {
            "variant_details_count": len(details),
            "variant_interpretation_count": len(interps),
            "actionable_variants": actionable,
            "variant_details": details,
            "variant_interpretation": interps,
        }

    async def get_patient_demographics(self, patient_id: str) -> PatientDemographics | None:
        """Get patient demographics from Fabric UDF."""
        rows = await self._get_structured_data(patient_id, "patient_demographics")
        if rows:
            return rows[0]
        return await super().get_patient_demographics(patient_id)

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

        lock = self._read_locks.setdefault(patient_id, asyncio.Lock())

        async with lock:
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
