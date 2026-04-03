# Shared date parsing utilities for GYN Tumor Board tools.
#
# Centralizes the date parsing logic used by tumor_markers.py and
# pretumor_board_checklist.py to avoid divergent behavior.

import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

# Common date formats seen in Epic/Caboodle exports (time-aware first)
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d-%b-%Y",
]


def parse_datetime(date_str: str) -> datetime:
    """Parse a date string into a datetime. Returns datetime.min on failure.

    Used by tumor_markers.py for sorting data points.
    """
    cleaned = date_str.strip()
    try:
        return datetime.fromisoformat(cleaned).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse date: %r", date_str)
    return datetime.min


def parse_date(date_str: str) -> date | None:
    """Parse a date string into a date. Returns None on failure.

    Used by pretumor_board_checklist.py for staleness calculations.
    """
    if not date_str:
        return None
    cleaned = date_str.strip().replace("Z", "")
    if "+" in cleaned and cleaned.index("+") > 10:
        cleaned = cleaned[: cleaned.index("+")]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None
