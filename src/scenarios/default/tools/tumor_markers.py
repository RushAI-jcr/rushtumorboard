# Tumor Marker Trending Tool for GYN Oncology Tumor Board
#
# Retrieves and analyzes tumor marker trends from Epic lab data.
# Supports CA-125, HE4, hCG, and other GYN-relevant markers.
# Calculates nadir, doubling time, and GCIG response criteria.

import asyncio
import json
import logging
import math

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

from utils.date_utils import parse_datetime as _parse_date

from .note_type_constants import GENERAL_CLINICAL_TYPES, ONCOLOGY_TYPES, TELEPHONE_TYPES
from .validation import validate_patient_id

logger = logging.getLogger(__name__)


def create_plugin(plugin_config: PluginConfiguration):
    return TumorMarkerPlugin(plugin_config)


# Known GYN tumor markers and their reference ranges
GYN_MARKERS = {
    "ca-125": {"upper_normal": 35.0, "unit": "U/mL"},
    "ca125": {"upper_normal": 35.0, "unit": "U/mL"},
    "he4": {"upper_normal": 140.0, "unit": "pmol/L"},
    "hcg": {"upper_normal": 5.0, "unit": "mIU/mL"},
    "beta-hcg": {"upper_normal": 5.0, "unit": "mIU/mL"},
    "cea": {"upper_normal": 5.0, "unit": "ng/mL"},
    "afp": {"upper_normal": 10.0, "unit": "ng/mL"},
    "ldh": {"upper_normal": 250.0, "unit": "U/L"},
    "inhibin": {"upper_normal": 10.0, "unit": "pg/mL"},
    "scc": {"upper_normal": 1.5, "unit": "ng/mL"},
}


class TumorMarkerPlugin:
    # Note types and keywords for layered fallback when no lab data exists
    # NoteType values confirmed in real Epic Caboodle exports at Rush:
    #   "Progress Notes"    — all outpatient visits incl. new-patient H&Ps
    #   "Consults"          — confirmed; IR/other service consults with inline labs
    #   "ED Provider Notes" — confirmed for germ cell/complex patients
    #   "Discharge Summary" — inpatient stays often summarize marker trends
    #   "H&P"               — kept for non-Rush sources (FHIR/Fabric)
    _MARKER_NOTE_TYPES: list[str] = list(GENERAL_CLINICAL_TYPES + ONCOLOGY_TYPES + TELEPHONE_TYPES)
    _MARKER_KEYWORDS = [
        "ca-125", "ca125", "ca 125", "he4", "he-4",
        "hcg", "beta-hcg", "cea", "afp", "ca-19", "ca19",
        "ca 27", "ca2729", "ca 15", "ca153", "tumor marker",
        "scc", "scc-ag", "squamous cell carcinoma antigen",
    ]

    def __init__(self, config: PluginConfiguration):
        self.chat_ctx = config.chat_ctx
        self.data_access = config.data_access

    async def _get_marker_notes_fallback(self, patient_id: str, marker: str) -> str | None:
        """Layer 2/3 fallback: extract marker mentions from clinical notes.

        When no structured lab data exists, search H&P, Progress Notes, and Consults
        for tumor marker values mentioned by physicians.

        Returns a JSON string with extracted note excerpts for the LLM to parse.
        """
        accessor = self.data_access.clinical_note_accessor

        # Build keyword list: requested marker + all known marker keywords
        keywords = [marker.lower()] + list(self._MARKER_KEYWORDS)

        notes = await accessor.get_clinical_notes_by_keywords(
            patient_id, self._MARKER_NOTE_TYPES, keywords
        )

        if not notes:
            return None

        # Return a structured summary for the caller
        excerpts = []
        for n in notes[:20]:  # Cap at 20 notes to avoid token overload
            note_type = n.get("NoteType", n.get("note_type", ""))
            date = n.get("EntryDate", n.get("date", ""))
            text = n.get("NoteText", n.get("note_text", n.get("text", "")))
            excerpts.append({"note_type": note_type, "date": date, "text_preview": text[:2000]})

        return json.dumps({
            "patient_id": patient_id,
            "marker": marker,
            "source": "clinical_notes_fallback",
            "source_description": (
                f"No structured lab data for {marker}. Found {len(notes)} clinical notes "
                f"mentioning tumor markers. Marker values may be embedded in physician notes."
            ),
            "note_excerpts": excerpts,
        }, indent=2)

    @kernel_function(
        description="Get tumor marker trends for a patient. "
        "Returns time series data for GYN tumor markers (CA-125, HE4, hCG, etc.) "
        "with trend analysis including nadir, doubling time, and GCIG response."
    )
    async def get_tumor_marker_trend(
        self,
        patient_id: str,
        marker: str = "CA-125",
    ) -> str:
        """Get tumor marker trend with analysis.

        Args:
            patient_id: The patient ID.
            marker: Marker name (CA-125, HE4, hCG, CEA, AFP, LDH, Inhibin, SCC). Default: CA-125.

        Returns:
            JSON with time series data and trend analysis.
        """
        if not validate_patient_id(patient_id):
            return json.dumps({"error": "Invalid patient ID."})

        # Validate marker against known GYN markers (soft warning — allow unknown markers)
        marker_key_norm = marker.lower().replace("-", "").replace(" ", "")
        known_keys = {k.replace("-", "").replace(" ", "") for k in GYN_MARKERS}
        if marker_key_norm not in known_keys:
            logger.warning(
                "Unrecognized tumor marker %r for patient %s; proceeding with best-effort lab lookup",
                marker, patient_id,
            )

        accessor = self.data_access.clinical_note_accessor

        # Layer 1: Get structured lab results — both calls are independent, gather concurrently
        labs_result, all_markers_result = await asyncio.gather(
            accessor.get_lab_results(patient_id, component_name=marker),
            accessor.get_tumor_markers(patient_id),
            return_exceptions=True,
        )
        if isinstance(labs_result, BaseException):
            labs_result = []
        if isinstance(all_markers_result, BaseException):
            all_markers_result = []
        labs = labs_result or [
            m for m in all_markers_result
            if marker.lower().replace("-", "") in
            m.get("ComponentName", m.get("component_name", "")).lower().replace("-", "")
        ]

        if not labs:
            # Layer 2/3: Fallback to clinical notes
            fallback = await self._get_marker_notes_fallback(patient_id, marker)
            if fallback:
                logger.info("Tumor marker fallback to clinical notes for %s/%s", patient_id, marker)
                return fallback
            return json.dumps({
                "patient_id": patient_id,
                "marker": marker,
                "error": f"No {marker} results found in labs or clinical notes.",
                "data_points": []
            })

        # Parse and sort data points
        data_points = []
        for lab in labs:
            date_str = lab.get("OrderDate", lab.get("date", lab.get("order_date", "")))
            value_str = lab.get("ResultValue", lab.get("result_value", lab.get("ORD_VALUE", "")))
            unit = lab.get("ResultUnit", lab.get("result_unit", lab.get("REFERENCE_UNIT", "")))
            flag = lab.get("AbnormalFlag", lab.get("abnormal_flag", lab.get("RESULT_FLAG_C", "")))

            try:
                value = float(str(value_str).replace(",", "").replace("<", "").replace(">", ""))
            except (ValueError, TypeError):
                continue

            data_points.append({
                "date": date_str,
                "value": value,
                "unit": unit,
                "abnormal_flag": flag,
            })

        # Sort by date (parse to handle mixed formats)
        data_points.sort(key=lambda x: _parse_date(x["date"]))

        if not data_points:
            return json.dumps({
                "patient_id": patient_id,
                "marker": marker,
                "error": f"No valid numeric {marker} values found.",
                "data_points": []
            })

        # Trend analysis
        analysis = self._analyze_trend(marker, data_points)

        result = {
            "patient_id": patient_id,
            "marker": marker.upper(),
            "data_points": data_points,
            "analysis": analysis,
        }

        logger.info("Tumor marker trend for %s/%s: %d data points", patient_id, marker, len(data_points))
        return json.dumps(result, indent=2)

    @kernel_function(
        description="Get all available tumor markers for a patient with summary statistics."
    )
    async def get_all_tumor_markers(self, patient_id: str) -> str:
        """Get summary of all tumor markers for a patient.

        Args:
            patient_id: The patient ID.

        Returns:
            JSON with all available marker summaries.
        """
        if not validate_patient_id(patient_id):
            return json.dumps({"error": "Invalid patient ID."})

        accessor = self.data_access.clinical_note_accessor

        tumor_markers_result, all_labs = await asyncio.gather(
            accessor.get_tumor_markers(patient_id),
            accessor.get_lab_results(patient_id),
            return_exceptions=True,
        )
        if isinstance(tumor_markers_result, BaseException):
            tumor_markers_result = []
        if isinstance(all_labs, BaseException):
            all_labs = []
        all_markers = tumor_markers_result if tumor_markers_result else all_labs

        if not all_markers:
            # Fallback to clinical notes
            fallback = await self._get_marker_notes_fallback(patient_id, "tumor markers")
            if fallback:
                logger.info("All tumor markers fallback to clinical notes for %s", patient_id)
                return fallback
            return json.dumps({
                "patient_id": patient_id,
                "markers": {},
                "message": "No tumor marker results found in labs or clinical notes."
            })

        # Group by marker name
        grouped = {}
        for lab in all_markers:
            name = lab.get("ComponentName", lab.get("component_name", "Unknown"))
            if name not in grouped:
                grouped[name] = []

            value_str = lab.get("ResultValue", lab.get("result_value", ""))
            date_str = lab.get("OrderDate", lab.get("date", ""))
            unit = lab.get("ResultUnit", lab.get("result_unit", ""))

            try:
                value = float(str(value_str).replace(",", "").replace("<", "").replace(">", ""))
                grouped[name].append({"date": date_str, "value": value, "unit": unit})
            except (ValueError, TypeError):
                continue

        # Build summary for each marker
        summaries = {}
        for name, points in grouped.items():
            points.sort(key=lambda x: _parse_date(x["date"]))
            values = [p["value"] for p in points]
            summaries[name] = {
                "count": len(points),
                "first_value": values[0] if values else None,
                "first_date": points[0]["date"] if points else None,
                "latest_value": values[-1] if values else None,
                "latest_date": points[-1]["date"] if points else None,
                "nadir": min(values) if values else None,
                "peak": max(values) if values else None,
                "unit": points[0]["unit"] if points else "",
                "trend": self._simple_trend(values),
                "data_points": points,
            }

        return json.dumps({
            "patient_id": patient_id,
            "markers": summaries,
        }, indent=2)

    def _analyze_trend(self, marker: str, data_points: list[dict]) -> dict:
        """Analyze tumor marker trend."""
        values = [dp["value"] for dp in data_points]

        analysis = {
            "first_value": values[0],
            "latest_value": values[-1],
            "nadir": min(values),
            "peak": max(values),
            "trend_direction": self._simple_trend(values),
            "total_data_points": len(values),
        }

        # Reference range
        marker_key = marker.lower().replace("-", "").replace(" ", "")
        for key, info in GYN_MARKERS.items():
            if key.replace("-", "") == marker_key:
                analysis["upper_normal"] = info["upper_normal"]
                analysis["latest_above_normal"] = values[-1] > info["upper_normal"]
                break

        # GCIG response criteria (for CA-125)
        if "ca" in marker.lower() and "125" in marker.lower() and len(values) >= 2:
            analysis["gcig_response"] = self._gcig_response(values)

        # Doubling time (if rising)
        if len(values) >= 2 and values[-1] > values[-2]:
            dt = self._doubling_time(data_points)
            if dt is not None:
                analysis["doubling_time_days"] = round(dt, 1)

        # Percent change from baseline
        if values[0] > 0:
            analysis["percent_change_from_baseline"] = round(
                ((values[-1] - values[0]) / values[0]) * 100, 1
            )

        # Percent change from nadir
        nadir_val = min(values)
        if nadir_val > 0:
            analysis["percent_change_from_nadir"] = round(
                ((values[-1] - nadir_val) / nadir_val) * 100, 1
            )

        return analysis

    @staticmethod
    def _simple_trend(values: list[float]) -> str:
        """Determine simple trend direction."""
        if len(values) < 2:
            return "insufficient data"

        # Compare last value to first
        first, last = values[0], values[-1]
        if first == 0:
            return "rising" if last > 0 else "stable"

        pct_change = ((last - first) / first) * 100

        if pct_change <= -50:
            return "declining significantly"
        elif pct_change <= -10:
            return "declining"
        elif pct_change <= 10:
            return "stable"
        elif pct_change <= 50:
            return "rising"
        else:
            return "rising significantly"

    @staticmethod
    def _gcig_response(values: list[float]) -> str:
        """Apply GCIG CA-125 response criteria.

        GCIG criteria:
        - Response: >=50% decrease from pretreatment, confirmed at 28 days
        - Progression: >=2x increase from nadir (nadir must be normal) or
                       >=2x increase from nadir if nadir never normalized
        """
        if len(values) < 2:
            return "insufficient data"

        baseline = values[0]
        nadir = min(values)
        latest = values[-1]

        if baseline > 0 and latest <= baseline * 0.5:
            return "response (>=50% decrease from baseline)"
        elif nadir > 0 and latest >= nadir * 2:
            return "progression (>=2x increase from nadir)"
        elif latest <= 35:
            return "normalized"
        else:
            return "no definitive response or progression"

    @staticmethod
    def _doubling_time(data_points: list[dict]) -> float | None:
        """Calculate doubling time in days between last two rising values."""
        if len(data_points) < 2:
            return None

        # Find last two points where value increased
        for i in range(len(data_points) - 1, 0, -1):
            v2 = data_points[i]["value"]
            v1 = data_points[i - 1]["value"]
            if v2 > v1 and v1 > 0:
                try:
                    d1 = _parse_date(data_points[i - 1]["date"])
                    d2 = _parse_date(data_points[i]["date"])
                    days = (d2 - d1).days
                    if days > 0:
                        return days * math.log(2) / math.log(v2 / v1)
                except (ValueError, TypeError):
                    pass
        return None
