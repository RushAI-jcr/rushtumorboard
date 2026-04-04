# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import os

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob.aio import BlobServiceClient
from fastapi import APIRouter, Request, Response

from data_models import mime_type

logger = logging.getLogger(__name__)


def patient_data_routes(blob_service_client: BlobServiceClient | None, chat_artifact_accessor=None):
    router = APIRouter()
    is_local_dev = os.getenv("LOCAL_DEV", "").lower() == "true"

    async def get_blob(request: Request, blob_path: str, container_name: str) -> Response:
        ''' Get a file generated from an Azure AI Agent '''

        # Auth guard – require Azure App Service authentication header (skip in local dev)
        if not is_local_dev:
            principal_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
            if not principal_id:
                return Response(status_code=401, content="Authentication required")

        filename = os.path.basename(blob_path)
        logger.info("Serving blob request (container=%s)", container_name)

        # Local dev: read from in-memory artifact store
        if is_local_dev and chat_artifact_accessor and container_name == "chat-artifacts":
            try:
                from data_models.chat_artifact import ChatArtifactIdentifier
                # blob_path format: base64_conv_id/patient_id/filename
                parts = blob_path.split("/", 2)
                if len(parts) == 3:
                    import base64
                    conv_id = base64.urlsafe_b64decode(parts[0]).decode("utf-8")
                    artifact_id = ChatArtifactIdentifier(
                        conversation_id=conv_id,
                        patient_id=parts[1],
                        filename=parts[2],
                    )
                    artifact = await chat_artifact_accessor.read(artifact_id)
                    return Response(
                        media_type=mime_type(filename),
                        content=artifact.data,
                        headers={"Content-Type": mime_type(filename), "Content-Disposition": f'attachment; filename="{filename}"'},
                    )
            except Exception:
                logger.exception("Error reading local artifact: %s", blob_path)
                return Response(status_code=404, content="Artifact not found")

        if not blob_service_client:
            return Response(status_code=404, content="Blob storage not available in local dev")

        try:
            container_client = blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_path)

            # Download the blob content
            blob = await blob_client.download_blob()
            blob_data = await blob.readall()

            # Set content type
            headers = {
                'Content-Type': mime_type(filename)
            }

            return Response(media_type=mime_type(filename), content=blob_data, headers=headers)
        except ResourceNotFoundError:
            return Response(status_code=404, content="Requested resource not found")

    @router.get("/chat_artifacts/{blob_path:path}")
    async def get_chat_artifact(request: Request, blob_path: str):
        return await get_blob(request, blob_path, container_name="chat-artifacts")

    @router.get("/patient_data/{blob_path:path}")
    async def get_patient_data(request: Request, blob_path: str):
        return await get_blob(request, blob_path, container_name="patient-data")

    return router


def get_chat_artifacts_url(blob_path: str) -> str:
    """Get the URL for a given blob path in chat artifacts."""
    if os.getenv("LOCAL_DEV", "").lower() == "true":
        return f"http://localhost:3000/chat_artifacts/{blob_path}"
    hostname = os.getenv("BACKEND_APP_HOSTNAME")
    return f"https://{hostname}/chat_artifacts/{blob_path}"


def get_patient_data_url(blob_path: str) -> str:
    """Get the URL for a given blob path."""
    if os.getenv("LOCAL_DEV", "").lower() == "true":
        return f"http://localhost:3000/patient_data/{blob_path}"
    hostname = os.getenv("BACKEND_APP_HOSTNAME")
    return f"https://{hostname}/patient_data/{blob_path}"
