# Pre-Tumor Board Procedure Pass Checklist
#
# Audits whether required labs, imaging, pathology, and consults are present
# and within recency thresholds for a Rush GYN Oncology Tumor Board case.
#
# Rush pre-meeting protocol (confirmed by clinical staff):
#   Labs:     CBC ≤14 days, CMP ≤14 days, CA-125 ≤28 days (ovarian),
#             hCG if germ cell/GTD, CEA/CA19-9 if mucinous
#   Imaging:  CT CAP ≤56 days (~8 wks), Pelvic MRI ≤42 days (~6 wks),
#             PET/CT if indicated, CXR if no CT chest
#   Path:     Surgical pathology report + IHC (MMR, p53, ER/PR, HER2, POLE/NGS)
#   Consults: GYN Onc surgery, Med Onc, Rad Onc (as applicable)

import asyncio
import json
import logging
from datetime import date

from semantic_kernel.functions import kernel_function

from data_models.chat_context import ChatContext
from data_models.clinical_note_accessor_protocol import ClinicalNoteAccessorProtocol
from data_models.data_access import DataAccess
from data_models.plugin_configuration import PluginConfiguration

from utils.date_utils import parse_date as _parse_date

from .note_type_constants import GENERAL_TIER_B_TYPES, ONCOLOGY_TIER_A_TYPES
from .validation import validate_patient_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rush Epic order codes (reference only — also used as lookup for checklist)
# ---------------------------------------------------------------------------
RUSH_ORDER_CODES = {
    # Labs
    "CBC":                "LAB002101",
    "CMP":                "LAB0000022",
    "CA-125":             "LAB0000338",
    "Beta-hCG":           "LAB0033506",
    "CEA":                "LAB003025",
    "CA19-9":             "LAB0082224",
    # Imaging
    "CT_CAP":             "RAD100623",
    "MRI_Pelvis_WW":      "RAD100865",
    "MRI_Pelvis_W":       "RAD100863",
    "CT_Chest_W":         "RAD100625",
    "CT_Chest_Screen":    "RADRAD300301",
    "PET_CT":             "RAD300085",
    # Pathology / molecular
    "Surg_Path":          "LAB1230001",
    "NGS":                "LABL0832245",
    "BRCA":               "LABRCBRCC",
    # Consults
    "GYN_Onc":            "REF100223",
    "Med_Onc":            "REF000054",
    "Rad_Onc":            "REF000095",
    "Genetics":           "REF000151",
    "Fertility":          "REF000038",
    "Palliative":         "REF000152",
    # Checklist display-name aliases (match _check_labs labels)
    "CA 19-9":            "LAB0082224",
    # Staging procedures
    "Cystoscopy":         "20000P",
    "Cystoscopy_Biopsy":  "52204PS",
    "Proctoscopy":        "45300P",
    "Sigmoidoscopy":      "GAS100012",
}

# ---------------------------------------------------------------------------
# Component name patterns for lab matching
# ---------------------------------------------------------------------------
_CBC_PATTERNS = [
    "wbc", "white blood", "hemoglobin", "hgb", "platelet",
    "neutrophil", "cbc", "basophil absolute", "eosinophil absolute",
    "lymphocyte absolute", "monocyte absolute",
]
_CMP_PATTERNS = [
    "creatinine", "egfr", "sodium", "potassium", "chloride",
    "co2", "bun", "glucose", "alt", "ast", "alkaline phosphatase",
    "bilirubin", "albumin", "total protein", "calcium", "cmp",
]
_CA125_PATTERNS = ["ca-125", "ca125", "ca 125"]
_HCG_PATTERNS = ["hcg", "beta-hcg", "bhcg", "beta hcg", "human chorionic"]
_CEA_PATTERNS = ["cea", "carcinoembryonic"]
_CA199_PATTERNS = ["ca19-9", "ca 19-9", "ca-19-9", "ca199"]
_HE4_PATTERNS = ["he4", "he-4", "human epididymis"]

# Pathology / molecular markers in lab results
_NGS_PATTERNS = ["ngs", "next generation", "genomic panel", "myriad", "foundation", "tempus",
                 "brca", "brca1", "brca2", "pole", "msi", "microsatellite"]

# Imaging procedure name patterns
_CT_CAP_PATTERNS = ["ct chest, abdomen and pelvis", "ct chest abdomen pelvis",
                    "ct chest abdomen & pelvis", "ct a/p", "ct cap",
                    "ct chest/abdomen/pelvis"]
_MRI_PEL_PATTERNS = ["mri pelvis", "mr pelvis", "mri of the pelvis"]
_PET_PATTERNS = ["pet", "pet-ct", "pet/ct", "pet scan"]
_CXR_PATTERNS = ["chest x-ray", "cxr", "chest radiograph", "pa chest",
                 "ct chest"]  # CT chest counts as chest imaging fallback

# Consult note type keywords (NoteType = "Consults" / "Consult Note" / note text)
_GYN_ONC_PATTERNS = ["gynecol", "gyn onc", "gynecologic oncol"]
_MED_ONC_PATTERNS = ["medical oncol", "hematol", "hematol/oncol", "hem/onc"]
_RAD_ONC_PATTERNS = ["radiation oncol", "rad onc", "radio oncol"]
_GENETICS_PATTERNS = ["genetic", "genetics", "risc", "lynch", "brca", "hereditary"]
_FERTILITY_PATTERNS = ["fertility", "reproductive", "infertil"]
_PALLIATIVE_PATTERNS = ["palliative", "hospice", "comfort care"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _most_recent_date(rows: list[dict], date_field: str) -> date | None:
    dates = [_parse_date(r.get(date_field, "")) for r in rows]
    valid = [d for d in dates if d]
    return max(valid) if valid else None


def _days_ago(d: date, as_of: date) -> int:
    return (as_of - d).days


def _status(present: bool, days: int | None, threshold: int | None) -> str:
    """Return ✓, ⚠, or ✗ with context."""
    if not present:
        return "✗ MISSING"
    if days is None:
        return "✓ present (date unknown)"
    if threshold and days > threshold:
        return f"⚠ STALE ({days}d ago — threshold {threshold}d)"
    return f"✓ current ({days}d ago)"


def _match_any(value: str, patterns: list[str]) -> bool:
    v = value.lower()
    return any(p in v for p in patterns)


def _match_lab_row(row: dict, patterns: list[str]) -> bool:
    """Match a lab row against patterns — checks ComponentName and (for clinical note
    fallback rows) also searches the NoteText."""
    if _match_any(row.get("ComponentName", row.get("component_name", "")), patterns):
        return True
    # For rows sourced from clinical notes, also search the note text
    if row.get("source") == "clinical_notes":
        return _match_any(row.get("NoteText", ""), patterns)
    return False


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

def create_plugin(plugin_config: PluginConfiguration) -> "PreTumorBoardChecklistPlugin":
    return PreTumorBoardChecklistPlugin(
        data_access=plugin_config.data_access,
        chat_ctx=plugin_config.chat_ctx,
    )


class PreTumorBoardChecklistPlugin:
    """
    Audits whether required data items are present and within recency thresholds
    for a Rush GYN Oncology Tumor Board case presentation.
    """

    def __init__(self, data_access: DataAccess, chat_ctx: ChatContext):
        self.data_access = data_access
        self.chat_ctx = chat_ctx

    @kernel_function(
        description=(
            "Run the Rush GYN Tumor Board pre-meeting procedure pass for a patient. "
            "Checks whether required labs (CBC, CMP, CA-125, hCG, CEA, CA19-9), imaging "
            "(CT CAP, MRI Pelvis, PET/CT), pathology report, molecular markers, and "
            "consult notes are present and within recency thresholds. "
            "Returns a structured checklist with ✓/⚠/✗ status for each item and "
            "a list of outstanding actions needed before the tumor board."
        )
    )
    async def get_pretumor_board_checklist(
        self,
        patient_id: str,
        cancer_type: str = "ovarian",
        as_of_date: str = "",
    ) -> str:
        """
        Run the pre-meeting procedure pass checklist.

        Args:
            patient_id:   Epic patient ID (UUID or synthetic ID).
            cancer_type:  "ovarian", "endometrial", "cervical", "vulvar", "germ_cell",
                          "mucinous", or "other". Controls which conditional items apply.
            as_of_date:   Reference date for staleness calculation (YYYY-MM-DD).
                          Defaults to today's date.

        Returns:
            Formatted checklist string with status for each required item.
        """
        if not validate_patient_id(patient_id):
            return json.dumps({"error": "Invalid patient ID."})

        as_of = _parse_date(as_of_date) or date.today()
        ctype = cancer_type.lower()

        accessor = self.data_access.clinical_note_accessor

        (
            labs, rad_reports, path_reports, all_notes,
            staging, medications,
        ) = await asyncio.gather(
            self._get_labs(accessor, patient_id),
            self._get_radiology(accessor, patient_id),
            self._get_pathology(accessor, patient_id),
            self._get_clinical_notes(accessor, patient_id),
            self._get_staging(accessor, patient_id),
            self._get_medications(accessor, patient_id),
        )

        checklist: list[dict] = []

        # ===== LABS =====
        checklist += self._check_labs(labs, ctype, as_of)

        # ===== IMAGING =====
        checklist += self._check_imaging(rad_reports, as_of)

        # ===== PATHOLOGY & MOLECULAR =====
        checklist += self._check_pathology(path_reports, labs, all_notes)

        # ===== STAGING =====
        checklist += self._check_staging(staging)

        # ===== MEDICATIONS =====
        checklist += self._check_medications(medications)

        # ===== CONSULTS =====
        checklist += self._check_consults(all_notes)

        # Build formatted output
        return self._format_checklist(patient_id, as_of, checklist, ctype)

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    async def _get_labs(self, accessor: ClinicalNoteAccessorProtocol, patient_id: str) -> list[dict]:
        """Get labs from structured lab_results.csv first, then fall back to clinical notes."""
        # All lab keywords to search for in clinical notes if structured data is missing
        all_lab_keywords = (
            list(_CBC_PATTERNS) + list(_CMP_PATTERNS) +
            list(_CA125_PATTERNS) + list(_HCG_PATTERNS) +
            list(_CEA_PATTERNS) + list(_CA199_PATTERNS) + list(_HE4_PATTERNS)
        )
        return await accessor.get_lab_results_with_notes_fallback(
            patient_id, component_name=None, keywords=all_lab_keywords,
        )

    async def _get_radiology(self, accessor: ClinicalNoteAccessorProtocol, patient_id: str) -> list[dict]:
        """Get radiology data: dedicated reports first, then clinical notes fallback."""
        reports = await accessor.get_radiology_reports(patient_id)
        if reports:
            return reports

        # Fallback: search all clinical note types for imaging references
        imaging_keywords = [
            p.lower() for p in
            _CT_CAP_PATTERNS + _MRI_PEL_PATTERNS + _PET_PATTERNS + _CXR_PATTERNS
        ]
        all_note_types = list(ONCOLOGY_TIER_A_TYPES + GENERAL_TIER_B_TYPES)
        notes = await accessor.get_clinical_notes_by_keywords(
            patient_id, all_note_types, imaging_keywords,
        )
        if notes:
            logger.info(
                "Imaging checklist fallback: found %d clinical notes with imaging for %s",
                len(notes), patient_id,
            )
            return [self._note_to_rad_format(n) for n in notes]

        return []

    @staticmethod
    def _note_to_rad_format(note: dict) -> dict:
        """Convert a clinical note to a radiology-report-like dict for checklist matching."""
        text = note.get("NoteText", note.get("text", note.get("note_text", ""))) or ""
        return {
            "ProcedureName": text[:500],
            "OrderDate": note.get("EntryDate", note.get("date", "")),
            "source": "clinical_notes",
        }

    async def _get_pathology(self, accessor: ClinicalNoteAccessorProtocol, patient_id: str) -> list[dict]:
        return await accessor.get_pathology_reports(patient_id)

    async def _get_clinical_notes(self, accessor: ClinicalNoteAccessorProtocol, patient_id: str) -> list[dict]:
        consult_types = (
            "Consults", "Consult Note", "Oncology Consultation",
            "Genetic Counseling", "Procedures",
        )
        return await accessor.get_clinical_notes_by_type(patient_id, consult_types)

    async def _get_staging(self, accessor: ClinicalNoteAccessorProtocol, patient_id: str) -> list[dict]:
        return await accessor.get_cancer_staging(patient_id)

    async def _get_medications(self, accessor: ClinicalNoteAccessorProtocol, patient_id: str) -> list[dict]:
        return await accessor.get_medications(patient_id)

    # ------------------------------------------------------------------
    # Lab checks
    # ------------------------------------------------------------------

    def _check_labs(self, labs: list[dict], ctype: str, as_of: date) -> list[dict]:
        results = []

        def _check(label: str, patterns: list[str], threshold: int, conditional: bool = False) -> dict:
            matched = [r for r in labs if _match_lab_row(r, patterns)]
            if not matched:
                present = False
                days = None
            else:
                most_recent = _most_recent_date(matched, "OrderDate")
                present = True
                days = _days_ago(most_recent, as_of) if most_recent else None
            order_code = RUSH_ORDER_CODES.get(label)
            return {
                "section": "Labs",
                "item": label,
                "order_code": order_code or "",
                "conditional": conditional,
                "present": present,
                "days_ago": days,
                "threshold_days": threshold,
                "status": _status(present, days, threshold),
            }

        results.append(_check("CBC", _CBC_PATTERNS, 14))
        results.append(_check("CMP", _CMP_PATTERNS, 14))

        # CA-125: required for ovarian/fallopian tube/peritoneal, optional others
        ca125_required = ctype in ("ovarian", "fallopian", "peritoneal", "other")
        results.append(_check("CA-125", _CA125_PATTERNS, 28, conditional=not ca125_required))

        # Beta-hCG: germ cell tumors and GTD/GTN — required
        results.append(_check(
            "Beta-hCG", _HCG_PATTERNS, 28,
            conditional=ctype not in ("germ_cell", "gtd", "gtn"),
        ))

        # SCC antigen: cervical squamous cell carcinoma
        if ctype == "cervical":
            results.append(_check("SCC-Ag", ["scc", "scc-ag", "squamous cell carcinoma antigen"], 28, conditional=False))

        # CEA: mucinous carcinoma
        results.append(_check("CEA", _CEA_PATTERNS, 28, conditional=ctype != "mucinous"))

        # CA 19-9: mucinous carcinoma
        results.append(_check("CA 19-9", _CA199_PATTERNS, 28, conditional=ctype != "mucinous"))

        # HE4: ovarian (optional but useful)
        results.append(_check("HE4", _HE4_PATTERNS, 28, conditional=True))

        return results

    # ------------------------------------------------------------------
    # Imaging checks
    # ------------------------------------------------------------------

    def _check_imaging(self, rad_reports: list[dict], as_of: date) -> list[dict]:
        results = []

        def _check_rad(label: str, patterns: list[str], threshold: int,
                       order_code: str, conditional: bool = False) -> dict:
            matched = []
            for r in rad_reports:
                proc = r.get("ProcedureName", "")
                if _match_any(proc, patterns):
                    matched.append(r)
            if not matched:
                present = False
                days = None
            else:
                most_recent = _most_recent_date(matched, "OrderDate")
                present = True
                days = _days_ago(most_recent, as_of) if most_recent else None
            return {
                "section": "Imaging",
                "item": label,
                "order_code": order_code,
                "conditional": conditional,
                "present": present,
                "days_ago": days,
                "threshold_days": threshold,
                "status": _status(present, days, threshold),
            }

        results.append(_check_rad(
            "CT Chest/Abdomen/Pelvis", _CT_CAP_PATTERNS, 56, "RAD100623",
        ))
        results.append(_check_rad(
            "MRI Pelvis", _MRI_PEL_PATTERNS, 42,
            "RAD100865 (w/wo) or RAD100863 (w/o)",
        ))
        results.append(_check_rad(
            "PET/CT", _PET_PATTERNS, 56, "RAD300085", conditional=True,
        ))
        results.append(_check_rad(
            "Chest imaging (CXR/CT chest)", _CXR_PATTERNS, 56,
            "RAD100625 or RADRAD300301", conditional=True,
        ))

        return results

    # ------------------------------------------------------------------
    # Pathology & molecular checks
    # ------------------------------------------------------------------

    def _check_pathology(
        self,
        path_reports: list[dict],
        labs: list[dict],
        notes: list[dict],
    ) -> list[dict]:
        results = []

        # Surgical pathology report
        path_present = len(path_reports) > 0
        results.append({
            "section": "Pathology",
            "item": "Surgical pathology report",
            "order_code": "LAB1230001",
            "conditional": False,
            "present": path_present,
            "days_ago": None,  # path reports don't expire
            "threshold_days": None,
            "status": "✓ present" if path_present else "✗ MISSING — required before tumor board",
        })

        # IHC markers — look in lab results AND pathology report text
        ihc_markers = {
            "MMR (MLH1/PMS2/MSH2/MSH6)": ["mlh1", "msh2", "msh6", "pms2", "mmr", "mismatch repair", "msi"],
            "p53 IHC":                   ["p53"],
            "ER/PR":                     ["estrogen receptor", "er ", "progesterone receptor", "pr "],
            "HER2":                      ["her2", "her-2", "erbb2"],
            "PD-L1":                     ["pd-l1", "pdl1", "pdl-1", "cps"],
            "Ki-67":                     ["ki67", "ki-67", "mib-1"],
            "FRα":                       ["folate receptor", "fra", "folr1"],
            "TMB":                       ["tmb", "tumor mutational burden"],
            "CCNE1":                     ["ccne1", "cyclin e"],
        }
        for marker, patterns in ihc_markers.items():
            # Check pathology report text
            found_in_path = any(
                _match_any(r.get("ReportText", ""), patterns)
                for r in path_reports
            )
            # Check lab results (IHC often comes through as lab component)
            found_in_labs = any(
                _match_any(r.get("ComponentName", ""), patterns)
                for r in labs
            )
            present = found_in_path or found_in_labs
            results.append({
                "section": "Pathology",
                "item": f"IHC — {marker}",
                "order_code": "",
                "conditional": False,
                "present": present,
                "days_ago": None,
                "threshold_days": None,
                "status": "✓ present in report" if present else "⚠ not confirmed in data",
            })

        # NGS / molecular panel
        ngs_in_labs = any(_match_any(r.get("ComponentName", ""), _NGS_PATTERNS) for r in labs)
        ngs_in_path = any(_match_any(r.get("ReportText", ""), _NGS_PATTERNS) for r in path_reports)
        ngs_in_notes = any(
            _match_any(
                r.get("NoteText", r.get("text", r.get("note_text", ""))),
                ["ngs", "next generation sequencing", "foundation one", "tempus", "guardant",
                 "caris", "neogenomics", "myriad", "brca1", "brca2", "pole mutation"]
            )
            for r in notes
        )
        results.append({
            "section": "Pathology",
            "item": "Tumor genomic panel (NGS/HRD)",
            "order_code": "LABL0832245",
            "conditional": False,
            "present": ngs_in_labs or ngs_in_path or ngs_in_notes,
            "days_ago": None,
            "threshold_days": None,
            "status": (
                "✓ evidence of NGS/molecular testing"
                if (ngs_in_labs or ngs_in_path or ngs_in_notes)
                else "⚠ not confirmed — order NGS panel or confirm prior results"
            ),
        })

        # Germline genetic testing
        germline_in_notes = any(
            _match_any(
                r.get("NoteText", r.get("text", r.get("note_text", ""))),
                ["germline", "brca1", "brca2", "lynch syndrome", "mlh1 mutation",
                 "invitae", "myriad hereditary", "genetic testing", "genetic counseling"]
            )
            for r in notes
        )
        germline_in_labs = any(
            _match_any(r.get("ComponentName", ""), ["brca", "germline", "hereditary"])
            for r in labs
        )
        results.append({
            "section": "Pathology",
            "item": "Germline genetic testing (BRCA/Lynch)",
            "order_code": "LABRCBRCC",
            "conditional": False,
            "present": germline_in_notes or germline_in_labs,
            "days_ago": None,
            "threshold_days": None,
            "status": (
                "✓ evidence of germline testing"
                if (germline_in_notes or germline_in_labs)
                else "⚠ not confirmed — refer to RISC clinic (REF000151)"
            ),
        })

        return results

    # ------------------------------------------------------------------
    # Staging checks
    # ------------------------------------------------------------------

    def _check_staging(self, staging: list[dict]) -> list[dict]:
        """Check for structured FIGO/TNM staging records in cancer_staging.csv."""
        results = []
        has_figo = any(r.get("FIGOStage") for r in staging)
        has_tnm = any(r.get("TNM_T") or r.get("StageGroup") for r in staging)
        results.append({
            "section": "Staging",
            "item": "FIGO staging",
            "order_code": "",
            "conditional": False,
            "present": has_figo,
            "days_ago": None,
            "threshold_days": None,
            "status": "✓ FIGO stage recorded" if has_figo else "⚠ no FIGO staging in structured data — confirm verbally",
        })
        results.append({
            "section": "Staging",
            "item": "TNM staging",
            "order_code": "",
            "conditional": True,
            "present": has_tnm,
            "days_ago": None,
            "threshold_days": None,
            "status": "✓ TNM staging recorded" if has_tnm else "⚠ no TNM staging in structured data",
        })
        return results

    # ------------------------------------------------------------------
    # Medication checks
    # ------------------------------------------------------------------

    def _check_medications(self, medications: list[dict]) -> list[dict]:
        """Check for systemic therapy medication records in medications.csv."""
        results = []
        chemo_patterns = ["chemotherapy", "antineoplastic", "immunotherapy", "targeted"]
        chemo = [m for m in medications if _match_any(m.get("OrderClass", ""), chemo_patterns)]
        results.append({
            "section": "Medications",
            "item": "Systemic therapy orders",
            "order_code": "",
            "conditional": True,
            "present": len(chemo) > 0,
            "days_ago": None,
            "threshold_days": None,
            "status": (
                f"✓ {len(chemo)} systemic therapy order(s) found"
                if chemo else "⚠ no systemic therapy orders in medication data"
            ),
        })
        return results

    # ------------------------------------------------------------------
    # Consult checks
    # ------------------------------------------------------------------

    def _check_consults(self, notes: list[dict]) -> list[dict]:
        results = []

        def _note_text(n: dict) -> str:
            return (n.get("NoteText") or n.get("text") or n.get("note_text") or "").lower()

        def _check_consult(label: str, patterns: list[str],
                           order_code: str, conditional: bool = False) -> dict:
            present = any(_match_any(_note_text(n), patterns) for n in notes)
            return {
                "section": "Consults",
                "item": label,
                "order_code": order_code,
                "conditional": conditional,
                "present": present,
                "days_ago": None,
                "threshold_days": None,
                "status": "✓ consult note present" if present else "⚠ not found in notes",
            }

        results.append(_check_consult(
            "GYN Oncology surgery", _GYN_ONC_PATTERNS, "REF100223",
        ))
        results.append(_check_consult(
            "Medical Oncology", _MED_ONC_PATTERNS, "REF000054",
        ))
        results.append(_check_consult(
            "Radiation Oncology", _RAD_ONC_PATTERNS, "REF000095", conditional=True,
        ))
        results.append(_check_consult(
            "Cancer Genetics (RISC clinic)", _GENETICS_PATTERNS, "REF000151", conditional=True,
        ))
        results.append(_check_consult(
            "Fertility preservation", _FERTILITY_PATTERNS, "REF000038",
            conditional=True,  # only relevant for premenopausal patients
        ))
        results.append(_check_consult(
            "Palliative care", _PALLIATIVE_PATTERNS, "REF000152", conditional=True,
        ))

        return results

    # ------------------------------------------------------------------
    # Formatter
    # ------------------------------------------------------------------

    def _format_checklist(
        self,
        patient_id: str,
        as_of: date,
        checklist: list[dict],
        ctype: str,
    ) -> str:
        lines = [
            "## Pre-Tumor Board Procedure Pass",
            f"**Patient:** {patient_id}",
            f"**Cancer type:** {ctype}",
            f"**As of:** {as_of.strftime('%m/%d/%Y')}",
            "",
        ]

        actions_needed: list[str] = []
        current_section = ""

        for item in checklist:
            section = item["section"]
            if section != current_section:
                lines.append(f"### {section}")
                current_section = section

            label = item["item"]
            status = item["status"]
            code = f" `{item['order_code']}`" if item["order_code"] else ""
            cond = " *(conditional)*" if item["conditional"] else ""
            lines.append(f"- {status} — **{label}**{code}{cond}")

            # Flag required (non-conditional) failures as actions needed
            if not item["conditional"] and (
                item["status"].startswith("✗") or item["status"].startswith("⚠ STALE")
            ):
                order_hint = f" [{item['order_code']}]" if item["order_code"] else ""
                actions_needed.append(f"• {label}{order_hint}: {status}")

        # Outstanding actions block
        lines.append("")
        if actions_needed:
            lines.append("### ⚠ Outstanding Actions Before Tumor Board")
            lines.extend(actions_needed)
        else:
            lines.append("### ✓ All required items present and current")
            lines.append("Patient data is complete for tumor board presentation.")

        return "\n".join(lines)
