# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import html

from data_models.patient_data import PatientDataSource
from routes.views.evidence import Evidence, find_evidence


def render_grounded_clinical_note(patient_id: str, note_dict: dict, source: PatientDataSource) -> str:
    """
    Renders a clinical note with highlighted evidences.
    """
    note_id = source.note_id
    evidences = _find_evidences_in_source(note_dict, source)
    note_text = str(note_dict.get("text") or "")
    highlighted_note_text = _highlight_note_text(note_text, evidences) if evidences \
        else html.escape(note_text) or "No text provided"

    safe_patient_id = html.escape(str(patient_id))
    safe_note_id = html.escape(str(note_id))
    safe_date = html.escape(str(note_dict.get("date", "N/A")))
    safe_note_type = html.escape(str(note_dict.get("note_type", "N/A")))

    return f"""
        <html>
            <head>
                <title>Clinical Note</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    html {{
                        margin: auto;
                        max-width: 800px;
                    }}
                    pre {{
                        white-space: pre-wrap;
                    }}
                    .highlight {{
                        background-color: yellow; /* Highlight color for evidence */
                        border-radius: 3px;
                        padding: 0 2px;
                    }}
                </style>
            </head>
            <body>
                <h1>Clinical Note</h1>
                <p>Patient ID: {safe_patient_id}</p>
                <p>Note ID: {safe_note_id}</p>
                <p>Date: {safe_date}</p>
                <p>Note Type: {safe_note_type}</p>
                <pre>{highlighted_note_text}</pre>
            </body>
        </html>
    """


def _find_evidences_in_source(note_dict: dict, source: PatientDataSource) -> list[Evidence]:
    if "text" not in note_dict:
        return []
    if source is None:
        return []
    if source.sentences is None or len(source.sentences) == 0:
        return []

    evidences = []
    for sentence in source.sentences:
        # Skip None sentences to avoid errors
        if sentence is None:
            continue

        evidence = find_evidence(sentence, note_dict["text"])
        if evidence:
            evidences.append(evidence)

    return evidences


def _highlight_note_text(note_text: str, evidences: list[Evidence]) -> str:
    """
    Highlight the clinical note text based on the provided evidences.

    Args:
        note_text (str): The clinical note text.
        evidences (list[Evidence]): List of evidence objects to highlight in the note.

    Returns:
        str: The highlighted clinical note text.
    """
    highlighted_note_text = ""
    highlighted_note_text_index = 0

    for evidence in evidences:
        # Add the text before the evidence to the highlighted note text
        highlighted_note_text += html.escape(note_text[highlighted_note_text_index:evidence.begin])
        highlighted_note_text_index = evidence.begin

        # Highlight the evidence in the note text
        highlighted_note_text += f"<span class=\"highlight\">{html.escape(note_text[evidence.begin:evidence.end])}</span>"
        highlighted_note_text_index = evidence.end

    # Add the remaining text after the last evidence
    highlighted_note_text += html.escape(note_text[highlighted_note_text_index:])

    return highlighted_note_text
