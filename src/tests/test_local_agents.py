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

    @pytest.mark.asyncio
    async def test_get_clinical_notes_by_type(self, caboodle):
        """Layer 2 fallback: filter clinical notes by NoteType."""
        notes = await caboodle.get_clinical_notes_by_type(PATIENT_ID, ["H&P", "Progress Notes"])
        assert len(notes) > 0
        for n in notes:
            note_type = n.get("NoteType", n.get("note_type", "")).lower()
            assert note_type in {"h&p", "progress notes"}

    @pytest.mark.asyncio
    async def test_get_clinical_notes_by_type_empty(self, caboodle):
        """Empty note_types list returns all notes."""
        all_notes = await caboodle.get_clinical_notes_by_type(PATIENT_ID, [])
        assert len(all_notes) > 0

    @pytest.mark.asyncio
    async def test_get_clinical_notes_by_keywords(self, caboodle):
        """Layer 3 fallback: filter notes by type AND keyword."""
        notes = await caboodle.get_clinical_notes_by_keywords(
            PATIENT_ID, ["Progress Notes", "H&P"], ["cancer"]
        )
        for n in notes:
            text = n.get("NoteText", n.get("note_text", n.get("text", ""))).lower()
            assert "cancer" in text

    @pytest.mark.asyncio
    async def test_get_clinical_notes_by_keywords_no_match(self, caboodle):
        """Keywords that don't appear should return empty list."""
        notes = await caboodle.get_clinical_notes_by_keywords(
            PATIENT_ID, ["Progress Notes"], ["xyznonexistent123"]
        )
        assert len(notes) == 0

    @pytest.mark.asyncio
    async def test_file_caching(self, caboodle):
        """Verify _read_file caches results — second call should hit cache."""
        # First call populates cache
        notes1 = await caboodle._read_file(PATIENT_ID, "clinical_notes")
        # Second call should return same object from cache
        notes2 = await caboodle._read_file(PATIENT_ID, "clinical_notes")
        assert notes1 is notes2  # Same object reference = cache hit


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
        from semantic_kernel import Kernel
        from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
        from semantic_kernel.contents.chat_history import ChatHistory

        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        credential = None

        kernel = Kernel()
        if api_key:
            # Use API key auth
            kernel.add_service(
                AzureChatCompletion(
                    service_id="default",
                    deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
                    endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                    api_version="2024-12-01-preview",
                    api_key=api_key,
                )
            )
        else:
            # Fall back to Azure CLI credential (token-based auth)
            from azure.identity.aio import AzureCliCredential, get_bearer_token_provider
            credential = AzureCliCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
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
        if credential:
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

    def test_clinical_guidelines_has_nccn_tool(self):
        """ClinicalGuidelines agent has nccn_guidelines tool binding."""
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
        os.environ.setdefault("EXCLUDED_AGENTS", "")
        from config import load_agent_config
        agents = load_agent_config("default")
        cg = next(a for a in agents if a["name"] == "ClinicalGuidelines")
        tool_names = [t["name"] for t in cg.get("tools", [])]
        assert "nccn_guidelines" in tool_names, f"Expected nccn_guidelines tool, got: {tool_names}"


# ---------------------------------------------------------------------------
# F. NCCN Guidelines Plugin
# ---------------------------------------------------------------------------


class TestNCCNGuidelines:
    """Test the NCCN guidelines Semantic Kernel plugin loads and returns correct data."""

    @pytest.fixture(scope="class")
    def plugin(self):
        """Create the NCCN guidelines plugin."""
        from scenarios.default.tools.nccn_guidelines import NCCNGuidelinesPlugin

        # Reset class-level cache to force fresh load
        NCCNGuidelinesPlugin._loaded = False
        NCCNGuidelinesPlugin._pages = {}
        NCCNGuidelinesPlugin._disease_index = {}
        NCCNGuidelinesPlugin._type_index = {}
        NCCNGuidelinesPlugin._keyword_index = {}
        NCCNGuidelinesPlugin._guidelines = []

        # Create a minimal PluginConfiguration
        from data_models.plugin_configuration import PluginConfiguration
        config = PluginConfiguration.__new__(PluginConfiguration)
        return NCCNGuidelinesPlugin(config)

    def test_guidelines_loaded(self, plugin):
        """At least 3 guidelines loaded with 100+ pages."""
        assert len(plugin._guidelines) >= 3
        assert len(plugin._pages) >= 100
        logger.info("Loaded %d guidelines, %d unique page codes", len(plugin._guidelines), len(plugin._pages))

    def test_disease_index_populated(self, plugin):
        """Disease index has endometrial, vaginal, and vulvar entries."""
        assert "endometrial_carcinoma" in plugin._disease_index
        assert "vaginal_cancer" in plugin._disease_index
        assert "vulvar_cancer" in plugin._disease_index

    @pytest.mark.asyncio
    async def test_lookup_endo1(self, plugin):
        """ENDO-1 returns algorithm page with decision tree."""
        result = await plugin.lookup_nccn_page("ENDO-1")
        data = json.loads(result)
        assert data["page_code"] == "ENDO-1"
        assert data["content_type"] == "algorithm"
        assert "decision_tree" in data
        assert len(data["decision_tree"].get("nodes", [])) > 0

    @pytest.mark.asyncio
    async def test_lookup_vag1(self, plugin):
        """VAG-1 returns vaginal cancer algorithm page."""
        result = await plugin.lookup_nccn_page("VAG-1")
        data = json.loads(result)
        assert data["page_code"] == "VAG-1"
        assert "vaginal" in data.get("disease", "").lower() or "vaginal" in data.get("guideline", "").lower()

    @pytest.mark.asyncio
    async def test_lookup_vulva1(self, plugin):
        """VULVA-1 returns vulvar cancer algorithm page."""
        result = await plugin.lookup_nccn_page("VULVA-1")
        data = json.loads(result)
        assert data["page_code"] == "VULVA-1"

    @pytest.mark.asyncio
    async def test_lookup_not_found(self, plugin):
        """Missing page code returns error with suggestions."""
        result = await plugin.lookup_nccn_page("ENDO-99")
        data = json.loads(result)
        assert "error" in data
        assert "available_codes_for_prefix" in data

    @pytest.mark.asyncio
    async def test_search_endometrial_adjuvant(self, plugin):
        """Search for endometrial adjuvant treatment returns relevant pages."""
        result = await plugin.search_nccn_guidelines("endometrial", "Stage IIIC adjuvant treatment")
        data = json.loads(result)
        assert data["results_count"] > 0
        codes = [r.get("page_code", "") for r in data["results"]]
        # Should include algorithm or principles pages
        assert any(c.startswith("ENDO") for c in codes), f"Expected ENDO pages, got: {codes}"

    @pytest.mark.asyncio
    async def test_search_vulvar_recurrent(self, plugin):
        """Search for vulvar recurrent cancer returns results."""
        result = await plugin.search_nccn_guidelines("vulvar", "recurrent vulvar cancer treatment")
        data = json.loads(result)
        assert data["results_count"] > 0

    @pytest.mark.asyncio
    async def test_systemic_therapy_endometrial_dmmr(self, plugin):
        """Systemic therapy query for dMMR endometrial returns immunotherapy options."""
        result = await plugin.get_nccn_systemic_therapy("endometrial", "recurrent", "dMMR,MSI-H")
        data = json.loads(result)
        assert "therapy_pages" in data
        assert len(data["therapy_pages"]) > 0
        # Should mention immunotherapy agents
        all_content = json.dumps(data).lower()
        assert any(drug in all_content for drug in ["dostarlimab", "pembrolizumab"]), \
            "Expected immunotherapy agents in dMMR systemic therapy results"

    @pytest.mark.asyncio
    async def test_systemic_therapy_not_found(self, plugin):
        """Nonexistent cancer type returns error with available diseases."""
        result = await plugin.get_nccn_systemic_therapy("pancreatic", "adjuvant")
        data = json.loads(result)
        assert "error" in data
        assert "available_diseases" in data

    @pytest.mark.asyncio
    async def test_response_caps_at_30k(self, plugin):
        """Responses don't exceed MAX_RESPONSE_CHARS."""
        result = await plugin.search_nccn_guidelines("endometrial", "treatment")
        assert len(result) <= 35_000  # Allow some overhead for JSON structure
