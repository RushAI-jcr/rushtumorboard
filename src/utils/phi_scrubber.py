"""Shared PHI scrubber for external API queries.

Strips potential Protected Health Information (PHI) from text before
sending queries to external APIs (PubMed, ClinicalTrials.gov, NCI, etc.).
Patterns are intentionally aggressive — false positives (removing a harmless
number) are acceptable; false negatives (leaking an MRN) are not.
"""

import re

_PHI_PATTERNS = [
    # US date formats: M/D/YY, MM/DD/YYYY, M-D-YYYY, etc.
    re.compile(r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b'),
    # ISO dates: 2024-01-15, 2024-01-15T10:30:00Z
    re.compile(r'\b\d{4}-\d{2}-\d{2}(?:T\S+)?\b'),
    # MRN-like numbers (5+ digits — validation.py accepts 5-digit MRNs)
    re.compile(r'\b\d{5,}\b'),
    # SYN-prefixed synthetic MRNs
    re.compile(r'\bSYN-\d{4}\b'),
    # Labeled patient identifiers: "Patient: John Smith", "Name: Jane Doe", "Pt: J. Smith"
    # Case-insensitive keyword, but name parts must be proper case (prevents matching MRN, BRCA, etc.)
    re.compile(r'(?:[Pp]atient|[Nn]ame|[Pp]t)\s*[:=]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+'),
]


def scrub_phi(text: str) -> str:
    """Remove PHI patterns from text before sending to external APIs.

    Returns the scrubbed text with collapsed whitespace.
    Safe to call on already-clean text (no-op).
    """
    result = text
    for pattern in _PHI_PATTERNS:
        result = pattern.sub('', result)
    # Collapse multiple spaces left by removals
    return re.sub(r'  +', ' ', result).strip()
