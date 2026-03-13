# Tumor Marker Trending Tool for GYN Oncology Tumor Board
#
# Retrieves and analyzes tumor marker trends from Epic lab data.
# Supports CA-125, HE4, hCG, and other GYN-relevant markers.
# Calculates nadir, doubling time, and GCIG response criteria.

import json
import logging
import math
from datetime import datetime

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

logger = logging.getLogger(__name__)

# Common date formats seen in Epic/Caboodle exports (time-aware first)
_DATE_FORMATS = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"]


def _parse_date(date_str: str) -> datetime:
    """Parse a date string, trying common formats. Returns datetime.min on failure."""
    # Strip timezone for naive datetime comparison
    cleaned = date_str.strip().replace("Z", "")
    # Remove timezone offset (+00:00, -05:00, etc.)
    if "+" in cleaned and cleaned.index("+") > 10:
        cleaned = cleaned[:cleaned.index("+")]
    elif cleaned.count("-") > 2:
        # Handle trailing -HH:MM timezone offset
        parts = cleaned.rsplit("-", 1)
        if len(parts[1]) <= 5 and ":" in parts[1]:
            cleaned = parts[0]

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        logger.warning(f"Could not parse date: {date_str!r}")
        return datetime.min


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
    def __init__(self, config: PluginConfiguration):
        self.chat_ctx = config.chat_ctx
        self.data_access = config.data_access

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
        accessor = self.data_access.clinical_note_accessor

        # Get lab results
        if hasattr(accessor, "get_lab_results"):
            labs = await accessor.get_lab_results(patient_id, component_name=marker)
        elif hasattr(accessor, "get_tumor_markers"):
            all_markers = await accessor.get_tumor_markers(patient_id)
            labs = [
                m for m in all_markers
                if marker.lower().replace("-", "") in
                   m.get("ComponentName", m.get("component_name", "")).lower().replace("-", "")
            ]
        else:
            return json.dumps({
                "patient_id": patient_id,
                "marker": marker,
                "error": "Data accessor does not support lab results.",
                "data_points": []
            })

        if not labs:
            return json.dumps({
                "patient_id": patient_id,
                "marker": marker,
                "error": f"No {marker} results found.",
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
        values = [dp["value"] for dp in data_points]
        analysis = self._analyze_trend(marker, data_points)

        result = {
            "patient_id": patient_id,
            "marker": marker.upper(),
            "data_points": data_points,
            "analysis": analysis,
        }

        logger.info(f"Tumor marker trend for {patient_id}/{marker}: {len(data_points)} data points")
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
        accessor = self.data_access.clinical_note_accessor

        if hasattr(accessor, "get_tumor_markers"):
            all_markers = await accessor.get_tumor_markers(patient_id)
        elif hasattr(accessor, "get_lab_results"):
            all_markers = await accessor.get_lab_results(patient_id)
        else:
            return json.dumps({
                "patient_id": patient_id,
                "error": "Data accessor does not support lab results.",
            })

        if not all_markers:
            return json.dumps({
                "patient_id": patient_id,
                "markers": {},
                "message": "No tumor marker results found."
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
            }

        return json.dumps({
            "patient_id": patient_id,
            "markers": summaries,
        }, indent=2)

    def _analyze_trend(self, marker: str, data_points: list[dict]) -> dict:
        """Analyze tumor marker trend."""
        values = [dp["value"] for dp in data_points]
        dates = [dp["date"] for dp in data_points]

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
    def _doubling_time(data_points: list[dict]):
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
