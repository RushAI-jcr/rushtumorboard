"""Shared filter helpers for clinical note accessor implementations.

Extracted from the three fallback accessors (blob, FHIR, Fabric) which previously
contained byte-for-byte duplicate filter logic (~80 lines × 3 = 240 lines).
All three now delegate here so field-name handling is consistent.
"""
from collections.abc import Sequence


def filter_notes_by_type(notes: list[dict], note_types: Sequence[str]) -> list[dict]:
    """Return notes whose NoteType matches any value in note_types (case-insensitive).

    Checks both Epic Caboodle key spellings: ``NoteType`` and ``note_type``.
    Returns all notes when *note_types* is empty.
    """
    if not note_types:
        return list(notes)
    type_set = {t.lower() for t in note_types}
    return [
        n for n in notes
        if n.get("NoteType", n.get("note_type", "")).lower() in type_set
    ]


def filter_notes_by_keywords(
    notes: list[dict],
    note_types: Sequence[str],
    keywords: Sequence[str],
) -> list[dict]:
    """Return notes matching the type filter AND containing at least one keyword.

    Applies :func:`filter_notes_by_type` first, then checks note text for any
    keyword (case-insensitive).  Checks ``NoteText``, ``note_text``, and ``text``
    key spellings — the same precedence used across all four accessor backends.
    Returns all type-matched notes when *keywords* is empty.
    """
    typed = filter_notes_by_type(notes, note_types)
    if not keywords:
        return typed
    kw_lower = [k.lower() for k in keywords]
    return [
        n for n in typed
        if any(
            kw in n.get("NoteText", n.get("note_text", n.get("text", ""))).lower()
            for kw in kw_lower
        )
    ]
