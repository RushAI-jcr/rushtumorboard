"""In-memory stubs for local development without Azure Blob Storage."""

import logging

from azure.core.exceptions import ResourceNotFoundError

from data_models.chat_artifact import ChatArtifact, ChatArtifactIdentifier
from data_models.chat_context import ChatContext

logger = logging.getLogger(__name__)


class InMemoryChatContextAccessor:
    """Chat context stored in a dict — survives within a process, lost on restart."""

    def __init__(self):
        self._store: dict[str, ChatContext] = {}

    async def read(self, conversation_id: str) -> ChatContext:
        if conversation_id in self._store:
            return self._store[conversation_id]
        return ChatContext(conversation_id)

    async def write(self, chat_ctx: ChatContext) -> None:
        self._store[chat_ctx.conversation_id] = chat_ctx

    async def archive(self, chat_ctx: ChatContext) -> None:
        self._store.pop(chat_ctx.conversation_id, None)


class InMemoryChatArtifactAccessor:
    """Chat artifacts stored in a dict — survives within a process, lost on restart."""

    def __init__(self):
        self._store: dict[str, bytes] = {}

    def get_blob_path(self, artifact_id: ChatArtifactIdentifier) -> str:
        return f"{artifact_id.conversation_id}/{artifact_id.patient_id}/{artifact_id.filename}"

    def get_url(self, artifact_id: ChatArtifactIdentifier) -> str:
        return f"local://{self.get_blob_path(artifact_id)}"

    async def read(self, artifact_id: ChatArtifactIdentifier) -> ChatArtifact:
        key = self.get_blob_path(artifact_id)
        if key not in self._store:
            raise ResourceNotFoundError(f"Artifact not found: {key}")
        return ChatArtifact(artifact_id=artifact_id, data=self._store[key])

    async def write(self, artifact: ChatArtifact) -> None:
        key = self.get_blob_path(artifact.artifact_id)
        self._store[key] = artifact.data

    async def archive(self, conversation_id: str) -> str:
        keys_to_remove = [k for k in self._store if k.startswith(f"{conversation_id}/")]
        for k in keys_to_remove:
            del self._store[k]
        return conversation_id


class StubBlobSasDelegate:
    """No-op SAS delegate for local dev — returns URLs as-is."""

    async def get_blob_sas_url(self, url: str, **kwargs) -> str:
        return url


class StubImageAccessor:
    """No-op image accessor — no images in local dev."""

    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]:
        return []
