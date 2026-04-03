"""Shared filter utilities for clinical note accessor classes.

Extracted from ClinicalNoteAccessor, FhirClinicalNoteAccessor, and
FabricClinicalNoteAccessor to eliminate byte-for-byte duplication of
get_clinical_notes_by_type and get_clinical_notes_by_keywords logic.
"""
import json
from collections.abc import Sequence


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
    return [
        note for note in notes
        if any(
            kw in (str(note.get("NoteText", note.get("text", note.get("note_text", ""))) or "")).lower()
            for kw in kw_lower
        )
    ]
