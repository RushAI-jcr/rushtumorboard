"""
Local integration tests for the GYN Tumor Board agents.
Bypasses Bot Framework and Azure Blob Storage — uses local CSV data and local accessors.

Usage:
    cd src
    python -m pytest tests/test_local_agents.py -v

Prerequisites:
    - Azure OpenAI endpoint and deployment configured in .env (or environment variables)
    - `az login` completed (for AzureCliCredential)
    - Synthetic patient data in ../infra/patient_data/
"""

import asyncio
import json
import logging
import os
import sys

import pytest

# Ensure src/ is on the path so imports work as they do in the main app
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(SRC_DIR, ".env"))

from data_models.epic.caboodle_file_accessor import CaboodleFileAccessor
from tests.local_accessors import create_local_data_access

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(SRC_DIR, "..", "infra", "patient_data")
PATIENT_ID = "patient_gyn_001"
PATIENT_ID_2 = "patient_gyn_002"
OUTPUT_DIR = os.path.join(SRC_DIR, "tests", "output")

CSV_FILE_TYPES = [
    "clinical_notes",
    "pathology_reports",
    "radiology_reports",
    "lab_results",
    "cancer_staging",
    "medications",
    "diagnoses",
]


@pytest.fixture(scope="session")
def data_dir():
    return os.path.abspath(DATA_DIR)


@pytest.fixture(scope="session")
def caboodle(data_dir):
    return CaboodleFileAccessor(data_dir=data_dir)


@pytest.fixture(scope="session")
def data_access(data_dir):
    return create_local_data_access(data_dir=data_dir, output_dir=OUTPUT_DIR)


# ---------------------------------------------------------------------------
# A. Validate synthetic data
# ---------------------------------------------------------------------------


class TestSyntheticData:
    """Verify that all 7 CSV types exist and are readable for both patients."""

    @pytest.mark.parametrize("patient_id", [PATIENT_ID, PATIENT_ID_2])
    @pytest.mark.parametrize("file_type", CSV_FILE_TYPES)
    def test_csv_exists(self, data_dir, patient_id, file_type):
        csv_path = os.path.join(data_dir, patient_id, f"{file_type}.csv")
        assert os.path.exists(csv_path), f"Missing: {csv_path}"

    @pytest.mark.parametrize("patient_id", [PATIENT_ID, PATIENT_ID_2])
    @pytest.mark.asyncio
    async def test_caboodle_reads_all_file_types(self, caboodle, patient_id):
        """CaboodleFileAccessor can read every CSV type without errors."""
        for file_type in CSV_FILE_TYPES:
            rows = await caboodle._read_file(patient_id, file_type)
            assert isinstance(rows, list), f"{file_type} did not return a list"
            assert len(rows) > 0, f"{file_type} returned 0 rows for {patient_id}"

    @pytest.mark.asyncio
    async def test_get_patients(self, caboodle):
        patients = await caboodle.get_patients()
        assert PATIENT_ID in patients
        assert PATIENT_ID_2 in patients

    @pytest.mark.asyncio
    async def test_get_metadata_list(self, caboodle):
        metadata = await caboodle.get_metadata_list(PATIENT_ID)
        assert len(metadata) > 0
        for item in metadata:
            assert "id" in item
            assert "type" in item


# ---------------------------------------------------------------------------
# B. Validate CaboodleFileAccessor GYN-specific methods
# ---------------------------------------------------------------------------


class TestCaboodleGynMethods:
    """Test the GYN-specific accessor methods on patient_gyn_001."""

    @pytest.mark.asyncio
    async def test_get_pathology_reports(self, caboodle):
        reports = await caboodle.get_pathology_reports(PATIENT_ID)
        assert len(reports) > 0
        # Should have ReportID or report_id
        first = reports[0]
        assert any(k in first for k in ("ReportID", "report_id", "id"))

    @pytest.mark.asyncio
    async def test_get_radiology_reports(self, caboodle):
        reports = await caboodle.get_radiology_reports(PATIENT_ID)
        assert len(reports) > 0

    @pytest.mark.asyncio
    async def test_get_lab_results(self, caboodle):
        labs = await caboodle.get_lab_results(PATIENT_ID)
        assert len(labs) > 0

    @pytest.mark.asyncio
    async def test_get_tumor_markers(self, caboodle):
        markers = await caboodle.get_tumor_markers(PATIENT_ID)
        assert len(markers) > 0
        # Should contain CA-125 or similar marker
        marker_names = [
            m.get("ComponentName", m.get("component_name", "")).lower()
            for m in markers
        ]
        assert any("ca-125" in n or "ca125" in n for n in marker_names), \
            f"Expected CA-125 in tumor markers, got: {marker_names}"

    @pytest.mark.asyncio
    async def test_get_cancer_staging(self, caboodle):
        staging = await caboodle.get_cancer_staging(PATIENT_ID)
        assert len(staging) > 0

    @pytest.mark.asyncio
    async def test_get_medications(self, caboodle):
        meds = await caboodle.get_medications(PATIENT_ID)
        assert len(meds) > 0

    @pytest.mark.asyncio
    async def test_get_diagnoses(self, caboodle):
        dx = await caboodle.get_diagnoses(PATIENT_ID)
        assert len(dx) > 0

    @pytest.mark.asyncio
    async def test_read_all(self, caboodle):
        notes = await caboodle.read_all(PATIENT_ID)
        assert len(notes) > 0
        # Each should be valid JSON
        for note_json in notes:
            parsed = json.loads(note_json)
            assert "id" in parsed
            assert "text" in parsed


# ---------------------------------------------------------------------------
# C. Validate local accessors
# ---------------------------------------------------------------------------


class TestLocalAccessors:
    """Test that local accessors work as drop-in replacements."""

    @pytest.mark.asyncio
    async def test_local_data_access_structure(self, data_access):
        """DataAccess dataclass is fully populated."""
        assert data_access.blob_sas_delegate is not None
        assert data_access.chat_artifact_accessor is not None
        assert data_access.chat_context_accessor is not None
        assert data_access.clinical_note_accessor is not None
        assert data_access.image_accessor is not None

    @pytest.mark.asyncio
    async def test_image_accessor_returns_empty(self, data_access):
        """LocalImageAccessor returns empty list (no GYN images)."""
        images = await data_access.image_accessor.get_metadata_list(PATIENT_ID)
        assert images == []

    @pytest.mark.asyncio
    async def test_blob_sas_delegate_passthrough(self, data_access):
        url = "https://example.com/blob/test.docx"
        result = await data_access.blob_sas_delegate.get_blob_sas_url(url)
        assert result == url

    @pytest.mark.asyncio
    async def test_chat_context_roundtrip(self, data_access):
        """Write and read back a ChatContext."""
        from data_models.chat_context import ChatContext
        ctx = ChatContext("test-conv-001")
        ctx.patient_id = PATIENT_ID
        await data_access.chat_context_accessor.write(ctx)
        loaded = await data_access.chat_context_accessor.read("test-conv-001")
        assert loaded.patient_id == PATIENT_ID

    @pytest.mark.asyncio
    async def test_chat_artifact_roundtrip(self, data_access):
        """Write and read back a ChatArtifact."""
        from data_models.chat_artifact import ChatArtifact, ChatArtifactIdentifier
        artifact_id = ChatArtifactIdentifier(
            conversation_id="test-conv-001",
            patient_id=PATIENT_ID,
            filename="test_output.json",
        )
        artifact = ChatArtifact(artifact_id=artifact_id, data=b'{"test": true}')
        await data_access.chat_artifact_accessor.write(artifact)
        loaded = await data_access.chat_artifact_accessor.read(artifact_id)
        assert loaded.data == b'{"test": true}'

    @pytest.mark.asyncio
    async def test_patient_data_load(self, data_access):
        """Simulate what PatientDataPlugin.load_patient_data does."""
        clinical_note_metadatas = await data_access.clinical_note_accessor.get_metadata_list(PATIENT_ID)
        image_metadatas = await data_access.image_accessor.get_metadata_list(PATIENT_ID)
        combined = clinical_note_metadatas + image_metadatas
        assert len(combined) > 0


# ---------------------------------------------------------------------------
# D. Validate Azure OpenAI connection (requires credentials)
# ---------------------------------------------------------------------------


class TestAzureOpenAI:
    """Test Azure OpenAI connectivity. Skipped if credentials are not configured."""

    @pytest.fixture(autouse=True)
    def check_azure_config(self):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
        if not endpoint or "<" in endpoint or not deployment:
            pytest.skip("Azure OpenAI not configured — set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME in .env")

    @pytest.mark.asyncio
    async def test_azure_openai_connection(self):
        """Create a Semantic Kernel and send a test message."""
        from azure.identity.aio import AzureCliCredential, get_bearer_token_provider
        from semantic_kernel import Kernel
        from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
        from semantic_kernel.contents.chat_history import ChatHistory

        credential = AzureCliCredential()
        token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

        kernel = Kernel()
        kernel.add_service(
            AzureChatCompletion(
                service_id="default",
                deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
                api_version="2025-04-01-preview",
                ad_token_provider=token_provider,
            )
        )

        chat_service: AzureChatCompletion = kernel.get_service(service_id="default")
        history = ChatHistory()
        history.add_system_message("You are a helpful assistant. Respond in one sentence.")
        history.add_user_message("What is 2 + 2?")

        response = await chat_service.get_chat_message_content(chat_history=history)
        assert response is not None
        assert len(response.content) > 0
        logger.info(f"Azure OpenAI response: {response.content}")
        await credential.close()


# ---------------------------------------------------------------------------
# E. Validate config loading
# ---------------------------------------------------------------------------


class TestConfig:
    """Test that agent configuration loads correctly."""

    def test_load_agent_config(self):
        """Load agents.yaml with dummy BOT_IDS."""
        os.environ.setdefault("SCENARIO", "default")
        os.environ.setdefault(
            "BOT_IDS",
            json.dumps({
                "Orchestrator": "dummy", "PatientHistory": "dummy",
                "OncologicHistory": "dummy", "Pathology": "dummy",
                "Radiology": "dummy", "PatientStatus": "dummy",
                "ClinicalGuidelines": "dummy", "ReportCreation": "dummy",
                "ClinicalTrials": "dummy", "MedicalResearch": "dummy",
            })
        )
        os.environ.setdefault("HLS_MODEL_ENDPOINTS", "{}")
        os.environ.setdefault("EXCLUDED_AGENTS", "")

        from config import load_agent_config
        agents = load_agent_config("default")
        agent_names = [a["name"] for a in agents]
        assert "Orchestrator" in agent_names
        assert "PatientHistory" in agent_names
        assert len(agents) == 10

    def test_load_agent_config_with_exclusion(self):
        """Excluding MedicalResearch leaves 9 agents."""
        os.environ["EXCLUDED_AGENTS"] = "MedicalResearch"
        from config import load_agent_config
        agents = load_agent_config("default")
        agent_names = [a["name"] for a in agents]
        assert "MedicalResearch" not in agent_names
        assert len(agents) == 9
        # Reset
        os.environ["EXCLUDED_AGENTS"] = ""
