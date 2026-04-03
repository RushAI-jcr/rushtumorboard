# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import json
import os

from azure.core.exceptions import ResourceNotFoundError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse

from data_models.chat_artifact import ChatArtifactFilename, ChatArtifactIdentifier
from data_models.data_access import DataAccess
from data_models.patient_data import PatientDataAnswer
from routes.views.grounded_clinical_note import render_grounded_clinical_note


def _require_authenticated_user(request: Request) -> str:
    """Reject requests without Azure App Service authentication."""
    principal_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "")
    if not principal_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal_id


def patient_data_answer_source_routes(data_access: DataAccess):
    """
    Create routes for viewing patient data answer sources.

    This code is not meant to be used in production. It is for demonstration purposes only.
    """
    router = APIRouter(dependencies=[Depends(_require_authenticated_user)])

    @router.get("/view/{conversation_id}/{patient_id}/patient_data_answer/{answer_id}/source/{source_index}.html")
    async def get_source(conversation_id: str, patient_id: str, answer_id: str, source_index: str):
        ''' Get a specific source from a patient timeline entry and render it as an HTML page. '''
        try:
            artifact_id = ChatArtifactIdentifier(
                conversation_id=conversation_id,
                patient_id=patient_id,
                filename=ChatArtifactFilename.PATIENT_DATA_ANSWERS
            )
            artifact = await data_access.chat_artifact_accessor.read(artifact_id)
            answers = json.loads(artifact.data.decode("utf-8"))
            if answer_id not in answers:
                return Response(status_code=404, content="Patient data answer not found.")
            answer = PatientDataAnswer.model_validate_json(answers[answer_id])
            try:
                source = answer.sources[int(source_index)]
            except (IndexError, ValueError):
                return Response(status_code=404, content="Source not found.")

            # Get the clinical note
            note_id = source.note_id
            note = await data_access.clinical_note_accessor.read(patient_id, note_id)
            note_dict = json.loads(note)

            body = render_grounded_clinical_note(patient_id, note_dict, source)
            return HTMLResponse(content=body)
        except ResourceNotFoundError:
            return Response(status_code=404, content="Patient data answer not found.")

    return router


def get_patient_data_answer_source_url(
    conversation_id: str, patient_id: str, answer_id: str, source_index: str
) -> str:
    """Get the URL for a patient clinical note."""
    hostname = os.getenv("BACKEND_APP_HOSTNAME")
    return f"https://{hostname}/view/{conversation_id}/{patient_id}/patient_data_answer/{answer_id}/source/{source_index}.html"
