# Local replacements for Azure Blob Storage-dependent accessors.
# Enables testing agents without Azure Blob Storage or Bot Framework.

import json
import logging
import os
from dataclasses import dataclass
from io import BytesIO

from data_models.chat_artifact import ChatArtifact, ChatArtifactIdentifier
from data_models.chat_context import ChatContext
from data_models.data_access import DataAccess
from data_models.epic.caboodle_file_accessor import CaboodleFileAccessor

logger = logging.getLogger(__name__)


class LocalChatArtifactAccessor:
    """Writes chat artifacts to a local output/ directory instead of Azure Blob Storage."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def get_blob_path(self, artifact_id: ChatArtifactIdentifier) -> str:
        return os.path.join(
            self.output_dir, artifact_id.conversation_id, artifact_id.patient_id, artifact_id.filename
        )

    def get_url(self, artifact_id: ChatArtifactIdentifier) -> str:
        return f"file://{os.path.abspath(self.get_blob_path(artifact_id))}"

    async def archive(self, conversation_id: str) -> str:
        logger.info(f"LocalChatArtifactAccessor.archive({conversation_id}) — no-op")
        return ""

    async def read(self, artifact_id: ChatArtifactIdentifier) -> ChatArtifact:
        path = self.get_blob_path(artifact_id)
        with open(path, "rb") as f:
            return ChatArtifact(artifact_id=artifact_id, data=f.read())

    async def write(self, artifact: ChatArtifact) -> None:
        path = self.get_blob_path(artifact.artifact_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(artifact.data)
        logger.info(f"Wrote artifact to {path}")


class LocalChatContextAccessor:
    """In-memory chat context storage for local testing."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def read(self, conversation_id: str) -> ChatContext:
        if conversation_id in self._store:
            from data_models.chat_context_accessor import ChatContextAccessor
            return ChatContextAccessor.deserialize(self._store[conversation_id])
        return ChatContext(conversation_id)

    async def write(self, chat_ctx: ChatContext) -> None:
        from data_models.chat_context_accessor import ChatContextAccessor
        self._store[chat_ctx.conversation_id] = ChatContextAccessor.serialize(chat_ctx)

    async def archive(self, chat_ctx: ChatContext) -> None:
        self._store.pop(chat_ctx.conversation_id, None)


class LocalImageAccessor:
    """Returns empty results — no CXR/radiology images in GYN synthetic data."""

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        return []

    def get_url(self, patient_id: str, filename: str) -> str:
        return ""

    async def read(self, patient_id: str, filename: str) -> BytesIO:
        return BytesIO()


class LocalBlobSasDelegate:
    """Passthrough — returns URLs unchanged since no SAS tokens needed locally."""

    async def get_blob_sas_url(self, url: str, **kwargs) -> str:
        return url


def create_local_data_access(
    data_dir: str | None = None,
    output_dir: str = "output",
) -> DataAccess:
    """Factory to create a DataAccess with all-local accessors.

    Args:
        data_dir: Path to patient data CSVs (defaults to infra/patient_data).
        output_dir: Directory for output artifacts.
    """
    if data_dir is None:
        data_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "infra", "patient_data"
        )

    return DataAccess(
        blob_sas_delegate=LocalBlobSasDelegate(),  # type: ignore[arg-type]
        chat_artifact_accessor=LocalChatArtifactAccessor(output_dir=output_dir),  # type: ignore[arg-type]
        chat_context_accessor=LocalChatContextAccessor(),  # type: ignore[arg-type]
        clinical_note_accessor=CaboodleFileAccessor(data_dir=data_dir),  # type: ignore[arg-type]
        image_accessor=LocalImageAccessor(),  # type: ignore[arg-type]
    )
