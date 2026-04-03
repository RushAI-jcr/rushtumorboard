# Epic Caboodle File Accessor
# Reads clinical data exported from Epic Caboodle as CSV or Parquet files.
# For testing/development: loads flat files from a local directory.
# For production: will be replaced by Fabric accessor querying Caboodle tables.

import asyncio
import csv
import json
import logging
import os
from collections import OrderedDict
from pathlib import Path
from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Optional parquet support — check availability without binding pd at module level
import importlib.util as _importlib_util
HAS_PANDAS: bool = _importlib_util.find_spec("pandas") is not None
del _importlib_util  # keep namespace clean


class CaboodleFileAccessor:
    """
    Reads Epic Caboodle data exported as CSV or Parquet files.

    Expected directory structure:
        {data_dir}/{patient_id}/
            clinical_notes.csv (or .parquet)
            pathology_reports.csv (or .parquet)
            radiology_reports.csv (or .parquet)
            lab_results.csv (or .parquet)
            cancer_staging.csv (or .parquet)
            medications.csv (or .parquet)
            diagnoses.csv (or .parquet)

    CSV column expectations (matching Caboodle naming conventions):

    clinical_notes.csv:
        NoteID, PatientID, NoteType, EntryDate, NoteText

    pathology_reports.csv:
        ReportID, PatientID, ProcedureName, OrderDate, ReportText

    radiology_reports.csv:
        ReportID, PatientID, ProcedureName, OrderDate, ReportText

    lab_results.csv:
        ResultID, PatientID, ComponentName, OrderDate, ResultValue, ResultUnit, ReferenceRange, AbnormalFlag

    cancer_staging.csv:
        PatientID, StageDate, StagingSystem, TNM_T, TNM_N, TNM_M, StageGroup, FIGOStage

    medications.csv:
        PatientID, MedicationName, StartDate, EndDate, Route, Dose, Frequency, OrderClass

    diagnoses.csv:
        PatientID, DiagnosisName, ICD10Code, DateOfEntry, Status
    """

    # Max patients' data kept in cache before evicting oldest (HIPAA: limit PHI in heap)
    _CACHE_MAX_PATIENTS: int = 5

    # Allowlist of valid file types for _read_file — prevents cross-patient PHI reads via
    # adversarial file_type values like "../../other_patient/lab_results".
    _VALID_FILE_TYPES: frozenset[str] = frozenset({
        "clinical_notes",
        "pathology_reports",
        "radiology_reports",
        "lab_results",
        "cancer_staging",
        "medications",
        "diagnoses",
    })

    _TUMOR_MARKER_NAMES: frozenset[str] = frozenset([
        "ca-125", "ca125", "ca 125",
        "he4", "he 4",
        "hcg", "beta-hcg", "beta hcg", "quant b-hcg",
        "cea",
        "afp", "alpha fetoprotein",
        "ldh",
        "scc", "scc ag", "squamous cell carcinoma antigen",
        "inhibin",
    ])

    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or os.getenv(
            "CABOODLE_DATA_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "infra", "patient_data")
        )
        self.data_dir = os.path.abspath(self.data_dir)
        self._resolved_data_dir = Path(self.data_dir).resolve()
        self._cache: OrderedDict[tuple[str, str], list[dict]] = OrderedDict()
        logger.info("CaboodleFileAccessor initialized with data_dir: %s", self.data_dir)

    async def get_patients(self) -> list[str]:
        """Get the list of patient IDs from subdirectories."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_patients_sync)

    def _get_patients_sync(self) -> list[str]:
        if not os.path.exists(self.data_dir):
            logger.warning("Data directory does not exist: %s", self.data_dir)
            return []
        patients = [
            d for d in os.listdir(self.data_dir)
            if os.path.isdir(os.path.join(self.data_dir, d))
        ]
        return sorted(patients)

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        """Get metadata list of all clinical documents for a patient.

        Returns unified list across clinical notes, pathology, radiology, and labs.
        Each item has 'id', 'type', and 'date' fields matching the existing interface.
        """
        # Read all file types concurrently
        notes, path_reports, rad_reports = await asyncio.gather(
            self._read_file(patient_id, "clinical_notes"),
            self._read_file(patient_id, "pathology_reports"),
            self._read_file(patient_id, "radiology_reports"),
        )

        metadata = []
        for row in notes:
            metadata.append({
                "id": row.get("NoteID", row.get("note_id", row.get("id", ""))),
                "type": row.get("NoteType", row.get("note_type", "clinical note")),
                "date": row.get("EntryDate", row.get("date", "")),
            })
        for row in path_reports:
            metadata.append({
                "id": row.get("ReportID", row.get("report_id", row.get("id", ""))),
                "type": "pathology report",
                "date": row.get("OrderDate", row.get("date", "")),
            })
        for row in rad_reports:
            metadata.append({
                "id": row.get("ReportID", row.get("report_id", row.get("id", ""))),
                "type": "radiology report",
                "date": row.get("OrderDate", row.get("date", "")),
            })

        # Sort unified list chronologically (oldest → newest) so agents see progression over time
        metadata.sort(key=lambda m: m.get("date", ""))
        return metadata

    async def read(self, patient_id: str, note_id: str) -> str:
        """Read a single clinical document by ID. Returns JSON string matching existing format."""
        # Search across all document types
        for file_type in ["clinical_notes", "pathology_reports", "radiology_reports"]:
            rows = await self._read_file(patient_id, file_type)
            for row in rows:
                row_id = row.get("NoteID", row.get("ReportID", row.get("note_id", row.get("report_id", row.get("id", "")))))
                if str(row_id) == str(note_id):
                    return json.dumps(self._normalize_to_note(row, file_type))

        logger.warning("Note %s not found for patient %s", note_id, patient_id)
        return json.dumps({"id": note_id, "text": "", "date": "", "note_type": "unknown"})

    async def read_all(self, patient_id: str) -> list[str]:
        """Read all clinical documents for a patient. Returns list of JSON strings."""
        file_types = ["clinical_notes", "pathology_reports", "radiology_reports"]
        results = await asyncio.gather(*(self._read_file(patient_id, ft) for ft in file_types))

        all_notes = []
        for file_type, rows in zip(file_types, results):
            for row in rows:
                note = self._normalize_to_note(row, file_type)
                all_notes.append(json.dumps(note))

        return all_notes

    # --- GYN-specific data accessors ---

    async def get_pathology_reports(self, patient_id: str) -> list[dict]:
        """Get pathology reports for a patient."""
        return await self._read_file(patient_id, "pathology_reports")

    async def get_radiology_reports(self, patient_id: str) -> list[dict]:
        """Get radiology reports for a patient."""
        return await self._read_file(patient_id, "radiology_reports")

    async def get_lab_results(self, patient_id: str, component_name: str | None = None) -> list[dict]:
        """Get lab results, optionally filtered by component name (e.g., 'CA-125')."""
        labs = await self._read_file(patient_id, "lab_results")
        if component_name:
            labs = [
                lab for lab in labs
                if component_name.lower() in lab.get("ComponentName", lab.get("component_name", "")).lower()
            ]
        return labs

    async def get_tumor_markers(self, patient_id: str) -> list[dict]:
        """Get tumor marker results (CA-125, HE4, hCG, CEA, AFP, LDH)."""
        labs = await self._read_file(patient_id, "lab_results")
        return [
            lab for lab in labs
            if any(
                marker in lab.get("ComponentName", lab.get("component_name", "")).lower()
                for marker in CaboodleFileAccessor._TUMOR_MARKER_NAMES
            )
        ]

    async def get_cancer_staging(self, patient_id: str) -> list[dict]:
        """Get cancer staging records (FIGO and TNM)."""
        return await self._read_file(patient_id, "cancer_staging")

    async def get_medications(self, patient_id: str, order_class: str | None = None) -> list[dict]:
        """Get medications, optionally filtered by order class (e.g., 'Chemotherapy')."""
        meds = await self._read_file(patient_id, "medications")
        if order_class:
            meds = [
                med for med in meds
                if order_class.lower() in med.get("OrderClass", med.get("order_class", "")).lower()
            ]
        return meds

    async def get_diagnoses(self, patient_id: str) -> list[dict]:
        """Get diagnosis list."""
        return await self._read_file(patient_id, "diagnoses")

    async def get_clinical_notes_by_type(
        self, patient_id: str, note_types: Sequence[str]
    ) -> list[dict]:
        """Get clinical notes filtered by NoteType.

        Args:
            patient_id: The patient ID.
            note_types: List of NoteType values to include (e.g., ["H&P", "Progress Notes"]).

        Returns:
            List of note dicts matching the given NoteTypes.
        """
        notes = await self._read_file(patient_id, "clinical_notes")
        if not note_types:
            return notes
        type_set = {t.lower() for t in note_types}
        return [
            n for n in notes
            if n.get("NoteType", n.get("note_type", "")).lower() in type_set
        ]

    async def get_clinical_notes_by_keywords(
        self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]
    ) -> list[dict]:
        """Get clinical notes filtered by NoteType AND containing any keyword in text.

        Args:
            patient_id: The patient ID.
            note_types: List of NoteType values to search within.
            keywords: List of keywords — note is included if any keyword appears in NoteText.

        Returns:
            List of note dicts matching both NoteType and keyword criteria.
        """
        notes = await self.get_clinical_notes_by_type(patient_id, note_types)
        if not keywords:
            return notes
        kw_lower = [k.lower() for k in keywords]
        return [
            n for n in notes
            if any(
                kw in n.get("NoteText", n.get("note_text", n.get("text", ""))).lower()
                for kw in kw_lower
            )
        ]

    # --- Internal helpers ---

    async def _read_file(self, patient_id: str, file_type: str) -> list[dict]:
        """Read a CSV or Parquet file for a patient. Returns list of dicts.

        Results are cached per (patient_id, file_type) since clinical data
        is immutable within a session. Eliminates redundant I/O when multiple
        agents read the same file.
        """
        if file_type not in self._VALID_FILE_TYPES:
            raise ValueError(
                f"Invalid file_type {file_type!r}. Must be one of: {sorted(self._VALID_FILE_TYPES)}"
            )

        cache_key = (patient_id, file_type)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)  # LRU: mark as recently used
            return self._cache[cache_key]

        # Validate patient_id to prevent path traversal
        patient_dir = os.path.join(self.data_dir, patient_id)
        if not Path(patient_dir).resolve().is_relative_to(self._resolved_data_dir):
            raise ValueError(f"Invalid patient_id {patient_id!r}: path traversal detected")

        # Try parquet first, then CSV — use executor to avoid blocking the event loop
        parquet_path = os.path.join(patient_dir, f"{file_type}.parquet")
        csv_path = os.path.join(patient_dir, f"{file_type}.csv")

        loop = asyncio.get_running_loop()
        parquet_exists, csv_exists = await asyncio.gather(
            loop.run_in_executor(None, os.path.exists, parquet_path),
            loop.run_in_executor(None, os.path.exists, csv_path),
        )

        if parquet_exists and HAS_PANDAS:
            rows = await self._read_parquet(parquet_path, patient_id)
        elif csv_exists:
            rows = await self._read_csv(csv_path, patient_id)
        elif file_type == "clinical_notes":
            # Fallback: read legacy JSON files from clinical_notes/ subdirectory
            rows = await self._read_legacy_json(patient_id)
        else:
            rows = []

        # Evict oldest entries if we've exceeded the per-patient limit
        patients_in_cache = dict.fromkeys(k[0] for k in self._cache)  # preserves insertion order
        if patient_id not in patients_in_cache and len(patients_in_cache) >= self._CACHE_MAX_PATIENTS:
            oldest_patient = next(iter(patients_in_cache))
            evict_keys = [k for k in list(self._cache) if k[0] == oldest_patient]
            for k in evict_keys:
                del self._cache[k]
            logger.info("Cache evicted %d entries for patient %s (limit: %d patients)", len(evict_keys), oldest_patient, self._CACHE_MAX_PATIENTS)

        self._cache[cache_key] = rows
        return rows

    async def _read_csv(self, filepath: str, patient_id: str) -> list[dict]:
        """Read a CSV file and return list of dicts."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._read_csv_sync, filepath, patient_id)
        except Exception as e:
            logger.error("Error reading CSV %s: %s", filepath, e)
            return []

    def _read_csv_sync(self, filepath: str, patient_id: str) -> list[dict]:
        """Synchronous CSV read."""
        rows = []
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter by patient_id if the file contains multiple patients
                row_patient = row.get("PatientID", row.get("patient_id", patient_id))
                if str(row_patient) == str(patient_id):
                    rows.append(dict(row))
        return rows

    async def _read_parquet(self, filepath: str, patient_id: str) -> list[dict]:
        """Read a Parquet file and return list of dicts."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._read_parquet_sync, filepath, patient_id)
        except Exception as e:
            logger.error("Error reading Parquet %s: %s", filepath, e)
            return []

    def _read_parquet_sync(self, filepath: str, patient_id: str) -> list[dict]:
        """Synchronous Parquet read."""
        import pandas as pd  # local import: caller already checked HAS_PANDAS
        df = pd.read_parquet(filepath)
        # Filter by patient_id if column exists
        patient_col = None
        for col in ["PatientID", "patient_id", "PAT_ID"]:
            if col in df.columns:
                patient_col = col
                break
        if patient_col:
            df = df[df[patient_col].astype(str) == str(patient_id)]
        else:
            logger.warning("No patient ID column found in %s. Returning all rows.", filepath)
        return df.to_dict("records")  # type: ignore[return-value]

    async def _read_legacy_json(self, patient_id: str) -> list[dict]:
        """Read legacy JSON clinical notes (backward compatibility with existing sample data)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_legacy_json_sync, patient_id)

    def _read_legacy_json_sync(self, patient_id: str) -> list[dict]:
        notes_dir = os.path.join(self.data_dir, patient_id, "clinical_notes")
        if not os.path.exists(notes_dir):
            return []

        notes_dir_resolved = Path(notes_dir).resolve()
        notes = []
        for filename in sorted(os.listdir(notes_dir)):
            if filename.endswith(".json"):
                filepath = os.path.join(notes_dir, filename)
                if not Path(filepath).resolve().is_relative_to(notes_dir_resolved):
                    logger.warning("Skipping file outside notes directory: %s", filename)
                    continue
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        note = json.load(f)
                        note.setdefault("id", filename.replace(".json", ""))
                        notes.append(note)
                except Exception as e:
                    logger.error("Error reading %s: %s", filepath, e)
        return notes

    def _normalize_to_note(self, row: dict, file_type: str) -> dict:
        """Normalize a row from any file type to the standard note format: {id, date, note_type, text}."""
        if file_type == "clinical_notes":
            return {
                "id": row.get("NoteID", row.get("note_id", row.get("id", ""))),
                "date": row.get("EntryDate", row.get("date", "")),
                "note_type": row.get("NoteType", row.get("note_type", "clinical note")),
                "text": row.get("NoteText", row.get("note_text", row.get("text", ""))),
            }
        elif file_type == "pathology_reports":
            return {
                "id": row.get("ReportID", row.get("report_id", row.get("id", ""))),
                "date": row.get("OrderDate", row.get("date", "")),
                "note_type": "pathology report",
                "text": row.get("ReportText", row.get("report_text", row.get("text", ""))),
            }
        elif file_type == "radiology_reports":
            return {
                "id": row.get("ReportID", row.get("report_id", row.get("id", ""))),
                "date": row.get("OrderDate", row.get("date", "")),
                "note_type": "radiology report",
                "text": row.get("ReportText", row.get("report_text", row.get("text", ""))),
            }
        else:
            return {
                "id": row.get("id", ""),
                "date": row.get("date", ""),
                "note_type": file_type,
                "text": json.dumps(row),
            }
