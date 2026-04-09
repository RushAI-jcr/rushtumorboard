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
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Sequence

from data_models.patient_demographics import PatientDemographics

logger = logging.getLogger(__name__)

# Optional parquet support — check availability without binding pd at module level
import importlib.util as _importlib_util  # noqa: E402
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

    patient_demographics.csv (optional — populated from Epic PAT table or Excel import):
        PatientID, MRN, PatientName, DOB, Sex

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

    variant_details.csv (optional — genomic variant calls from NGS/Tempus/Foundation):
        PatientID, VARIANT_ID, VARIANT_NAME, DISPLAY_NAME, VARIANT_TYPE, GENOME_ASSEMBLY,
        CHROMOSOME, START_POSITION, GENE, REFERENCE_ALLELE, OBSERVED_ALLELE,
        ALLELIC_READ_DEPTH, DNA_CHANGE, DNA_VAR_TYPE, TRANSCRIPT_REF_SEQ,
        TRANSCRIPT_SYSTEM, AMINO_ACID_CHANGE, ALLELIC_FREQUENCY, GENOMIC_SOURCE,
        METHOD_TYPE, ASSESSMENT, STDRD_AMINO_ACID_CHANGE, MOLECULAR_CONSEQUENCE,
        CMPT_AMINO_ACID_START_CODON, CMPT_AMINO_ACID_END_CODON,
        CMPT_AMINO_ACID_REFERENCE, CMPT_AMINO_ACID_ALTERNATE, ENTRY_SOURCE,
        STDRD_TRANSCRIPT_REF_SEQ

    variant_interpretation.csv (optional — clinical significance narratives per variant):
        VARIANT_ID, PatientID, CONCATENATED_TEXT
    """

    # Max patients' data kept in cache before evicting oldest (HIPAA: limit PHI in heap)
    _CACHE_MAX_PATIENTS: int = 5

    # Allowlist of valid file types for _read_file — prevents cross-patient PHI reads via
    # adversarial file_type values like "../../other_patient/lab_results".
    _VALID_FILE_TYPES: frozenset[str] = frozenset({
        "patient_demographics",
        "clinical_notes",
        "pathology_reports",
        "radiology_reports",
        "lab_results",
        "cancer_staging",
        "medications",
        "diagnoses",
        "variant_details",
        "variant_interpretation",
    })

    # Known GYN oncology genes — variants in these genes are always surfaced as actionable.
    # Covers: hereditary syndromes (BRCA, Lynch), targeted therapy targets (HER2, NTRK),
    # molecular classification (POLE, TP53, MMR), and common GYN somatic drivers.
    _GYN_ONCOLOGY_GENES: frozenset[str] = frozenset({
        # Hereditary / germline
        "BRCA1", "BRCA2", "MLH1", "MSH2", "MSH6", "PMS2", "EPCAM",
        "RAD51C", "RAD51D", "BRIP1", "PALB2", "ATM", "CHEK2",
        "STK11", "PTEN", "TP53", "MUTYH", "RAD50",
        # Molecular classification (endometrial)
        "POLE",
        # Targeted therapy targets
        "ERBB2", "HER2", "NTRK1", "NTRK2", "NTRK3",
        "PIK3CA", "KRAS", "BRAF", "FGFR2", "FGFR3",
        "CCNE1", "CDK4", "CDK6",
        # Common GYN somatic drivers
        "ARID1A", "CTNNB1", "FBXW7", "PPP2R1A", "RB1",
        "NF1", "CDKN2A", "CDKN2B", "APC",
        # Immuno markers
        "CD274",  # PD-L1
        # HRD-related
        "RAD51B", "FANCA", "FANCC",
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
        # ctDNA / Signatera
        "signatera", "ctdna", "natera", "mrd",
    ])

    # Map file_type → column name containing the date to filter on
    _DATE_COLUMNS: dict[str, list[str]] = {
        "clinical_notes": ["EntryDate", "entry_date", "date"],
        "pathology_reports": ["OrderDate", "order_date", "date"],
        "radiology_reports": ["OrderDate", "order_date", "date"],
        "lab_results": ["OrderDate", "order_date", "date"],
        "cancer_staging": ["StageDate", "stage_date", "date"],
        "medications": ["StartDate", "start_date", "date"],
        "diagnoses": ["DateOfEntry", "date_of_entry", "date"],
    }

    # Per-file-type lookback windows (in days) from the reference date.
    # None = no date filter (use all data).
    _DEFAULT_LOOKBACK: dict[str, int | None] = {
        "clinical_notes": 90,
        "lab_results": 365,
        "pathology_reports": None,   # all — always relevant
        "radiology_reports": None,   # all — always relevant
        "cancer_staging": None,      # all
        "medications": None,         # all
        "diagnoses": None,           # all
        "patient_demographics": None,  # no date filtering
        "variant_details": None,       # all — static molecular results
        "variant_interpretation": None,  # all — static molecular results
    }

    def __init__(self, data_dir: str | None = None, reference_date: str | None = None):
        """
        Args:
            data_dir: Path to patient CSV data.
            reference_date: ISO date (YYYY-MM-DD) for date window filtering.
                Typically today or the tumor board date. Reads TUMOR_BOARD_DATE env
                var as fallback. When set, per-file-type lookback windows are applied:
                  - clinical_notes: 90 days
                  - lab_results: 365 days (1 year for trends)
                  - pathology/radiology/staging/meds/dx: all (no filter)
        """
        self.data_dir = data_dir or os.getenv(
            "CABOODLE_DATA_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "infra", "patient_data")
        )
        self.data_dir = os.path.abspath(self.data_dir)
        self._resolved_data_dir = Path(self.data_dir).resolve()
        self._cache: OrderedDict[tuple[str, str], list[dict]] = OrderedDict()
        self._mrn_index: dict[str, str] | None = None  # lazy MRN→GUID index
        self._mrn_index_lock = asyncio.Lock()

        # Reference date for per-file-type lookback windows
        ref_date_str = reference_date or os.getenv("TUMOR_BOARD_DATE")
        if ref_date_str:
            self._reference_date = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
            logger.info("Reference date for lookback windows: %s", self._reference_date)
        else:
            self._reference_date = None

        logger.info("CaboodleFileAccessor initialized with data_dir: %s", self.data_dir)

    async def resolve_patient_id(self, identifier: str) -> str:
        """Resolve a patient identifier (GUID or MRN) to the canonical PatientID folder name.

        If the identifier matches an existing patient folder, returns it as-is.
        Otherwise, scans patient_demographics.csv files for a matching MRN and
        returns the corresponding PatientID (GUID).

        Also called inside _read_file as defense-in-depth — the second call is
        idempotent (hits the fast path since the folder exists after first resolution).
        """
        # Fast path: identifier is already a valid folder name
        candidate = Path(os.path.join(self.data_dir, identifier)).resolve()
        if not candidate.is_relative_to(self._resolved_data_dir):
            raise ValueError(f"Invalid identifier {identifier!r}: path traversal detected")
        if candidate.is_dir():
            return identifier

        # Build MRN→GUID index lazily (once per accessor lifetime), guarded by lock
        if self._mrn_index is None:
            async with self._mrn_index_lock:
                if self._mrn_index is None:  # double-check after acquiring lock
                    loop = asyncio.get_running_loop()
                    self._mrn_index = await loop.run_in_executor(None, self._build_mrn_index_sync)

        mrn_index = self._mrn_index or {}
        resolved = mrn_index.get(identifier)
        if resolved:
            logger.debug("Resolved MRN ***%s → PatientID %s", identifier[-4:], resolved)
            return resolved

        # No match found — return as-is (will fail downstream with empty results)
        return identifier

    def _build_mrn_index_sync(self) -> dict[str, str]:
        """Scan all patient folders for MRN→PatientID mappings from demographics CSVs."""
        index: dict[str, str] = {}
        if not os.path.exists(self.data_dir):
            return index
        for folder in os.listdir(self.data_dir):
            demo_path = os.path.join(self.data_dir, folder, "patient_demographics.csv")
            if not os.path.isfile(demo_path):
                continue
            try:
                with open(demo_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        mrn = row.get("MRN", "").strip()
                        if mrn:
                            index[mrn] = folder
            except (OSError, csv.Error, UnicodeDecodeError) as exc:
                logger.warning("Could not read demographics for %s: %s", folder, exc)
        logger.info("Built MRN→PatientID index: %d entries", len(index))
        return index

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

    async def get_lab_results_with_notes_fallback(
        self,
        patient_id: str,
        component_name: str | None = None,
        keywords: Sequence[str] | None = None,
    ) -> list[dict]:
        """Get lab results from lab_results.csv first, then fall back to clinical notes.

        This method is designed for callers (like the pre-tumor board checklist) that
        need to find lab values even when they are only documented in physician notes
        rather than as structured lab rows.

        Args:
            patient_id: The patient ID.
            component_name: Optional component filter for structured labs (e.g., 'CA-125').
            keywords: Keywords to search in clinical notes. If None, uses component_name.

        Returns:
            List of dicts. Structured lab results come first; if empty, falls back to
            clinical note excerpts with source='clinical_notes' marker.
        """
        # Layer 1: structured lab_results.csv
        labs = await self.get_lab_results(patient_id, component_name)
        if labs:
            return labs

        # Layer 2: search clinical notes for lab values
        search_keywords = list(keywords) if keywords else []
        if component_name and component_name.lower() not in [k.lower() for k in search_keywords]:
            search_keywords.insert(0, component_name)
        if not search_keywords:
            return []

        lab_note_types = [
            "Progress Notes", "Progress Note", "H&P", "History and Physical",
            "Oncology Consultation", "Consults", "Discharge Summary",
            "ED Provider Notes", "Telephone",
        ]
        notes = await self.get_clinical_notes_by_keywords(patient_id, lab_note_types, search_keywords)
        if not notes:
            return []

        logger.info(
            "Lab fallback to clinical notes for %s (keywords=%s): found %d notes",
            patient_id, search_keywords[:3], len(notes),
        )

        # Convert note excerpts to lab-like dicts so callers can process uniformly
        results = []
        for n in notes[:20]:
            results.append({
                "ComponentName": component_name or ", ".join(search_keywords[:3]),
                "OrderDate": n.get("EntryDate", n.get("date", "")),
                "ResultValue": "",
                "ResultUnit": "",
                "ReferenceRange": "",
                "AbnormalFlag": "",
                "source": "clinical_notes",
                "NoteType": n.get("NoteType", n.get("note_type", "")),
                "NoteText": n.get("NoteText", n.get("note_text", n.get("text", "")))[:2000],
            })

        return results

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

    async def get_variant_details(self, patient_id: str, gene: str | None = None) -> list[dict]:
        """Get genomic variant details (somatic/germline), optionally filtered by gene."""
        variants = await self._read_file(patient_id, "variant_details")
        if gene:
            gene_lower = gene.lower()
            variants = [
                v for v in variants
                if gene_lower in v.get("GENE", v.get("gene", "")).lower()
            ]
        return variants

    async def get_variant_interpretation(self, patient_id: str) -> list[dict]:
        """Get variant interpretation text (clinical significance narratives)."""
        return await self._read_file(patient_id, "variant_interpretation")

    async def get_molecular_data(self, patient_id: str) -> dict:
        """Get combined molecular/genomic data: variant details + interpretations.

        Returns a dict with 'variant_details' and 'variant_interpretation' keys,
        plus a 'variant_summary' with key actionable variants.
        """
        details, interps = await asyncio.gather(
            self.get_variant_details(patient_id),
            self.get_variant_interpretation(patient_id),
        )

        # Build interpretation lookup by VARIANT_ID
        interp_map: dict[str, str] = {}
        for row in interps:
            vid = row.get("VARIANT_ID", row.get("variant_id", ""))
            text = row.get("CONCATENATED_TEXT", row.get("concatenated_text", ""))
            if vid and text:
                interp_map[str(vid)] = text

        interpreted_vids = set(interp_map.keys())

        # Summarize actionable variants using clinically meaningful criteria:
        # 1. All germline variants (always relevant for hereditary cancer syndromes)
        # 2. Somatic variants in known GYN oncology genes
        # 3. Any variant with a clinical interpretation
        # 4. Loss-of-function variants (nonsense, frameshift) in any gene
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

            # Deduplicate by gene + change
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
        """Get patient demographics (MRN, name, DOB, sex) if available.

        Returns the first matching row as a dict, or None if the file is missing.
        The demographics CSV is optional — when absent, agents fall back to
        extracting MRN/name from clinical note text.
        """
        rows = await self._read_file(patient_id, "patient_demographics")
        return rows[0] if rows else None

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
        results = []
        for n in notes:
            text_lower = (n.get("NoteText", n.get("note_text", n.get("text", ""))) or "").lower()
            if any(kw in text_lower for kw in kw_lower):
                results.append(n)
        return results

    # --- Internal helpers ---

    def _apply_date_filter(self, rows: list[dict], file_type: str) -> list[dict]:
        """Filter rows using per-file-type lookback windows from the reference date.

        Lookback rules (from _DEFAULT_LOOKBACK):
          - clinical_notes: 90 days
          - lab_results: 365 days (1 year for trends)
          - pathology/radiology/staging/meds/dx: None (all data, no filter)
        """
        if self._reference_date is None:
            return rows

        lookback_days = self._DEFAULT_LOOKBACK.get(file_type)
        if lookback_days is None:
            return rows  # no filter for this file type

        date_cols = self._DATE_COLUMNS.get(file_type, [])
        if not date_cols:
            return rows

        window_start = self._reference_date - timedelta(days=lookback_days)

        filtered = []
        for row in rows:
            date_str = ""
            for col in date_cols:
                date_str = row.get(col, "")
                if date_str:
                    break
            if not date_str:
                filtered.append(row)  # keep rows without dates
                continue
            try:
                row_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                if window_start <= row_date <= self._reference_date:
                    filtered.append(row)
            except (ValueError, TypeError):
                filtered.append(row)  # keep rows with unparseable dates

        logger.info("Date filter %s: %d → %d rows (%d-day lookback, %s to %s)",
                     file_type, len(rows), len(filtered), lookback_days, window_start, self._reference_date)
        return filtered

    async def _read_file(self, patient_id: str, file_type: str) -> list[dict]:
        """Read a CSV or Parquet file for a patient. Returns list of dicts.

        Results are cached per (patient_id, file_type) since clinical data
        is immutable within a session. Eliminates redundant I/O when multiple
        agents read the same file.

        Note: calls resolve_patient_id() even though callers may have already
        resolved. This is intentional defense-in-depth — the second resolution
        is idempotent (fast-path: folder exists) and ensures _read_file is safe
        to call with raw MRN identifiers.
        """
        if file_type not in self._VALID_FILE_TYPES:
            raise ValueError(
                f"Invalid file_type {file_type!r}. Must be one of: {sorted(self._VALID_FILE_TYPES)}"
            )

        # Resolve MRN → GUID if the identifier doesn't match a folder
        patient_id = await self.resolve_patient_id(patient_id)

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

        # Apply date window filter if configured
        rows = self._apply_date_filter(rows, file_type)

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

    # Canonical column name mapping: alternate names → expected names.
    # Covers column differences across Caboodle export batches (e.g., March vs April).
    # Mirrored in scripts/validate_patient_csvs.py — update both when changing.
    _COLUMN_ALIASES: dict[str, str] = {
        "NOTE_ID": "NoteID",
        "NOTE_TYPE": "NoteType",
        "NOTE_DATE": "EntryDate",
        "CONCATENATED_TEXT": "NoteText",
        "STATUS": "Status",
        "Frequency (days)": "Frequency",
    }

    def _read_csv_sync(self, filepath: str, patient_id: str) -> list[dict]:
        """Synchronous CSV read with column name normalization."""
        rows = []
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize alternate column names to canonical names
                normalized = {}
                for k, v in row.items():
                    canonical = self._COLUMN_ALIASES.get(k, k)
                    normalized[canonical] = v
                # Filter by patient_id if the file contains multiple patients
                row_patient = normalized.get("PatientID", normalized.get("patient_id", patient_id))
                if str(row_patient) == str(patient_id):
                    rows.append(normalized)
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
