"""Shared filter utilities for clinical note accessor classes.

Extracted from ClinicalNoteAccessor, FhirClinicalNoteAccessor, and
FabricClinicalNoteAccessor to eliminate byte-for-byte duplication of
get_clinical_notes_by_type and get_clinical_notes_by_keywords logic.
"""
import hashlib
import json
import logging
from collections.abc import Sequence

logger = logging.getLogger(__name__)

# --- Constants for content-hash deduplication ---
_DEDUP_CHAR_WINDOW = 500
_TEXT_KEYS = ("ReportText", "NoteText", "note_text", "text")
_DATE_KEYS = ("OrderDate", "EntryDate", "date", "order_date")


def filter_notes_by_type(
    notes_json: Sequence[str | dict],
    note_types: Sequence[str],
) -> list[dict]:
    """Filter a list of raw note JSON strings or dicts by NoteType.

    Args:
        notes_json: List of note JSON strings or already-parsed dicts.
        note_types: NoteType values to include (case-insensitive).

    Returns:
        List of parsed note dicts matching any of the given note types.
        If note_types is empty, returns all notes as parsed dicts.
    """
    parsed = [json.loads(n) if isinstance(n, str) else n for n in notes_json]
    if not note_types:
        return parsed
    type_set = {t.lower() for t in note_types}
    return [
        note for note in parsed
        if note.get("NoteType", note.get("note_type", "")).lower() in type_set
    ]


def filter_notes_by_keywords(
    notes: list[dict],
    keywords: Sequence[str],
) -> list[dict]:
    """Filter a list of parsed note dicts by keyword presence in text.

    Args:
        notes: Already-parsed note dicts (output of filter_notes_by_type).
        keywords: Keywords to search for (case-insensitive).
                  A note is included if ANY keyword appears in its text.

    Returns:
        List of note dicts containing at least one keyword.
        If keywords is empty, returns all notes unchanged.
    """
    if not keywords:
        return notes
    kw_lower = [k.lower() for k in keywords]
    results = []
    for note in notes:
        text_lower = (str(note.get("NoteText", note.get("text", note.get("note_text", ""))) or "")).lower()
        if any(kw in text_lower for kw in kw_lower):
            results.append(note)
    return results


def deduplicate_notes(
    notes: list[dict],
    *,
    hash_chars: int = _DEDUP_CHAR_WINDOW,
    label: str = "notes",
) -> list[dict]:
    """Remove near-duplicate notes by content-hashing.

    GYN onc note templates copy pathology blocks, treatment timelines, and imaging
    summaries verbatim into every subsequent visit note — 15+ notes may contain
    identical clinical content. Dedup by hashing the first `hash_chars` characters
    of the note text and keeping only the NEWEST note for each unique hash.

    Args:
        notes: List of note/report dicts.
        hash_chars: Number of leading characters to hash (default 500).
        label: Label for log messages (e.g., "pathology", "clinical notes").

    Returns:
        Deduplicated list, preserving the newest note per content hash.
    """
    if len(notes) <= 1:
        return notes

    hash_to_newest: dict[str, dict] = {}
    for n in notes:
        text = next((n[k] for k in _TEXT_KEYS if k in n), "")
        if not text:
            # Never dedup empty-text notes against each other
            hash_to_newest[f"empty-{id(n)}"] = n  # unique key per empty note
            continue
        normalized = " ".join(text[:hash_chars].lower().split())
        content_hash = hashlib.md5(normalized.encode(), usedforsecurity=False).hexdigest()
        existing = hash_to_newest.get(content_hash)
        if existing is None:
            hash_to_newest[content_hash] = n
        else:
            existing_date = next((existing[k] for k in _DATE_KEYS if k in existing), "")
            new_date = next((n[k] for k in _DATE_KEYS if k in n), "")
            if new_date > existing_date:
                hash_to_newest[content_hash] = n

    deduped = list(hash_to_newest.values())
    if len(deduped) < len(notes):
        logger.info("Deduped %s: %d → %d unique", label, len(notes), len(deduped))
    return deduped
