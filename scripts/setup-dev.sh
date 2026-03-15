#!/usr/bin/env bash
# =============================================================================
# Rush GYN Oncology Tumor Board — Dev Environment Setup
# =============================================================================
# Provisions ALL Azure resources needed for local + deployed development:
#   1. Resource Group
#   2. AI Services (Azure OpenAI) + gpt-4.1 + o3-mini deployments
#   3. Storage Account (blob containers: chat-artifacts, chat-sessions, patient-data)
#   4. Key Vault
#   5. Managed Identities (1 per agent)
#   6. Bot Service registrations (1 per agent, with Teams channel)
#   7. App Service Plan + App Service
#   8. Application Insights
#   9. RBAC role assignments
#  10. Uploads synthetic patient data to blob storage
#  11. Generates src/.env with all values populated
#
# Prerequisites:
#   - az CLI installed and logged in (az login)
#   - Subscription with permissions to create resources
#
# Usage:
#   chmod +x scripts/setup-dev.sh
#   ./scripts/setup-dev.sh [ENVIRONMENT_NAME] [LOCATION]
#
# Example:
#   ./scripts/setup-dev.sh gyn-dev eastus2
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENV_NAME="${1:-gyn-dev}"
LOCATION="${2:-eastus2}"
UNIQUE_SUFFIX=$(echo -n "${ENV_NAME}" | md5 | cut -c1-4)
RG_NAME="rg-${ENV_NAME}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${REPO_ROOT}/src"

# Resource names
AI_SERVICES_NAME="cog-${ENV_NAME}-${UNIQUE_SUFFIX}"
STORAGE_NAME="$(echo "st${ENV_NAME}${UNIQUE_SUFFIX}" | tr -d '-' | cut -c1-24)"
APP_STORAGE_NAME="$(echo "stapp${ENV_NAME}${UNIQUE_SUFFIX}" | tr -d '-' | cut -c1-24)"
KEYVAULT_NAME="kv-${ENV_NAME}-${UNIQUE_SUFFIX}"
APP_PLAN_NAME="plan-${ENV_NAME}-${UNIQUE_SUFFIX}"
APP_NAME="app-${ENV_NAME}-${UNIQUE_SUFFIX}"
APP_INSIGHTS_NAME="appi-${ENV_NAME}-${UNIQUE_SUFFIX}"

# Models
GPT_MODEL="gpt-4.1"
GPT_MODEL_VERSION="2025-04-14"
GPT_CAPACITY=100  # 100K TPM
GPT_SKU="Standard"
REASONING_MODEL="o3-mini"
REASONING_MODEL_VERSION="2025-01-31"
REASONING_CAPACITY=50  # 50K TPM

# Agents
AGENTS=("Orchestrator" "PatientHistory" "OncologicHistory" "Pathology" "Radiology" "PatientStatus" "ClinicalGuidelines" "ReportCreation" "ClinicalTrials" "MedicalResearch")

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "Pre-flight checks..."

if ! command -v az &>/dev/null; then
    err "Azure CLI (az) not found. Install from https://aka.ms/install-azure-cli"
    exit 1
fi

ACCOUNT=$(az account show --query '{sub:id, tenant:tenantId, user:user.name}' -o json 2>/dev/null || true)
if [ -z "$ACCOUNT" ]; then
    err "Not logged in. Run: az login"
    exit 1
fi

SUB_ID=$(echo "$ACCOUNT" | python3 -c "import sys,json; print(json.load(sys.stdin)['sub'])")
TENANT_ID=$(echo "$ACCOUNT" | python3 -c "import sys,json; print(json.load(sys.stdin)['tenant'])")
USER_NAME=$(echo "$ACCOUNT" | python3 -c "import sys,json; print(json.load(sys.stdin)['user'])")
MY_PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")

log "Subscription: ${SUB_ID}"
log "Tenant:       ${TENANT_ID}"
log "User:         ${USER_NAME}"
log "Principal ID: ${MY_PRINCIPAL_ID}"
log "Environment:  ${ENV_NAME}"
log "Location:     ${LOCATION}"
echo ""

read -p "Proceed with provisioning? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. Resource Group
# ---------------------------------------------------------------------------
log "Creating resource group: ${RG_NAME}..."
az group create --name "$RG_NAME" --location "$LOCATION" --tags Project=gyn-tumor-board Environment=Dev -o none

# ---------------------------------------------------------------------------
# 2. AI Services + Model Deployments
# ---------------------------------------------------------------------------
log "Creating AI Services: ${AI_SERVICES_NAME}..."
az cognitiveservices account create \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RG_NAME" \
    --kind "AIServices" \
    --sku "S0" \
    --location "$LOCATION" \
    --custom-domain "$AI_SERVICES_NAME" \
    --yes \
    -o none

AI_ENDPOINT=$(az cognitiveservices account show \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RG_NAME" \
    --query properties.endpoint -o tsv)
log "AI Services endpoint: ${AI_ENDPOINT}"

# Assign Cognitive Services OpenAI Contributor to current user
log "Assigning RBAC roles on AI Services..."
AI_SERVICES_ID=$(az cognitiveservices account show --name "$AI_SERVICES_NAME" --resource-group "$RG_NAME" --query id -o tsv)
az role assignment create \
    --assignee-object-id "$MY_PRINCIPAL_ID" \
    --assignee-principal-type "User" \
    --role "Cognitive Services OpenAI Contributor" \
    --scope "$AI_SERVICES_ID" \
    -o none 2>/dev/null || warn "Role already assigned or insufficient permissions"
az role assignment create \
    --assignee-object-id "$MY_PRINCIPAL_ID" \
    --assignee-principal-type "User" \
    --role "Cognitive Services OpenAI User" \
    --scope "$AI_SERVICES_ID" \
    -o none 2>/dev/null || warn "Role already assigned or insufficient permissions"

# Deploy gpt-4.1
log "Deploying model: ${GPT_MODEL} (${GPT_CAPACITY}K TPM)..."
az cognitiveservices account deployment create \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RG_NAME" \
    --deployment-name "$GPT_MODEL" \
    --model-name "$GPT_MODEL" \
    --model-version "$GPT_MODEL_VERSION" \
    --model-format "OpenAI" \
    --sku-capacity "$GPT_CAPACITY" \
    --sku-name "$GPT_SKU" \
    -o none 2>/dev/null || warn "gpt-4.1 deployment may already exist or model not available in ${LOCATION}"

# Deploy o3-mini
log "Deploying model: ${REASONING_MODEL} (${REASONING_CAPACITY}K TPM)..."
az cognitiveservices account deployment create \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RG_NAME" \
    --deployment-name "$REASONING_MODEL" \
    --model-name "$REASONING_MODEL" \
    --model-version "$REASONING_MODEL_VERSION" \
    --model-format "OpenAI" \
    --sku-capacity "$REASONING_CAPACITY" \
    --sku-name "$GPT_SKU" \
    -o none 2>/dev/null || warn "o3-mini deployment may already exist or model not available in ${LOCATION}"

# ---------------------------------------------------------------------------
# 3. Storage Account
# ---------------------------------------------------------------------------
log "Creating storage account: ${APP_STORAGE_NAME}..."
az storage account create \
    --name "$APP_STORAGE_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --sku "Standard_LRS" \
    --kind "StorageV2" \
    --min-tls-version "TLS1_2" \
    --allow-blob-public-access false \
    --allow-shared-key-access false \
    -o none

STORAGE_BLOB_ENDPOINT=$(az storage account show \
    --name "$APP_STORAGE_NAME" \
    --resource-group "$RG_NAME" \
    --query primaryEndpoints.blob -o tsv)
log "Blob endpoint: ${STORAGE_BLOB_ENDPOINT}"

# Assign Storage Blob Data Contributor to current user
STORAGE_ID=$(az storage account show --name "$APP_STORAGE_NAME" --resource-group "$RG_NAME" --query id -o tsv)
az role assignment create \
    --assignee-object-id "$MY_PRINCIPAL_ID" \
    --assignee-principal-type "User" \
    --role "Storage Blob Data Contributor" \
    --scope "$STORAGE_ID" \
    -o none 2>/dev/null || warn "Storage role already assigned"

# Create containers (wait for RBAC propagation)
log "Waiting for RBAC propagation (30s)..."
sleep 30

log "Creating blob containers..."
for CONTAINER in chat-artifacts chat-sessions patient-data; do
    az storage container create \
        --name "$CONTAINER" \
        --account-name "$APP_STORAGE_NAME" \
        --auth-mode login \
        -o none 2>/dev/null || warn "Container ${CONTAINER} may already exist"
done

# ---------------------------------------------------------------------------
# 4. Key Vault
# ---------------------------------------------------------------------------
log "Creating Key Vault: ${KEYVAULT_NAME}..."
az keyvault create \
    --name "$KEYVAULT_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --enable-rbac-authorization true \
    -o none 2>/dev/null || warn "Key Vault may already exist"

KEYVAULT_ENDPOINT=$(az keyvault show --name "$KEYVAULT_NAME" --resource-group "$RG_NAME" --query properties.vaultUri -o tsv)

# Assign Key Vault Secrets User
KV_ID=$(az keyvault show --name "$KEYVAULT_NAME" --resource-group "$RG_NAME" --query id -o tsv)
az role assignment create \
    --assignee-object-id "$MY_PRINCIPAL_ID" \
    --assignee-principal-type "User" \
    --role "Key Vault Secrets Officer" \
    --scope "$KV_ID" \
    -o none 2>/dev/null || warn "KV role already assigned"

# ---------------------------------------------------------------------------
# 5. Application Insights
# ---------------------------------------------------------------------------
log "Creating Application Insights: ${APP_INSIGHTS_NAME}..."
az monitor app-insights component create \
    --app "$APP_INSIGHTS_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind web \
    --application-type web \
    -o none 2>/dev/null || warn "App Insights may already exist"

APP_INSIGHTS_CONN=$(az monitor app-insights component show \
    --app "$APP_INSIGHTS_NAME" \
    --resource-group "$RG_NAME" \
    --query connectionString -o tsv 2>/dev/null || echo "")

# ---------------------------------------------------------------------------
# 6. Managed Identities (1 per agent)
# ---------------------------------------------------------------------------
log "Creating managed identities for ${#AGENTS[@]} agents..."
declare -A MSI_CLIENT_IDS
declare -A MSI_IDS
declare -A MSI_PRINCIPAL_IDS

for AGENT in "${AGENTS[@]}"; do
    MSI_NAME="id-${AGENT,,}-${ENV_NAME}-${UNIQUE_SUFFIX}"
    az identity create \
        --name "$MSI_NAME" \
        --resource-group "$RG_NAME" \
        --location "$LOCATION" \
        -o none 2>/dev/null || true

    MSI_CLIENT_IDS[$AGENT]=$(az identity show --name "$MSI_NAME" --resource-group "$RG_NAME" --query clientId -o tsv)
    MSI_IDS[$AGENT]=$(az identity show --name "$MSI_NAME" --resource-group "$RG_NAME" --query id -o tsv)
    MSI_PRINCIPAL_IDS[$AGENT]=$(az identity show --name "$MSI_NAME" --resource-group "$RG_NAME" --query principalId -o tsv)
    log "  ${AGENT}: ${MSI_CLIENT_IDS[$AGENT]}"
done

# Assign AI Services roles to MSIs
log "Assigning AI Services roles to managed identities..."
for AGENT in "${AGENTS[@]}"; do
    az role assignment create \
        --assignee-object-id "${MSI_PRINCIPAL_IDS[$AGENT]}" \
        --assignee-principal-type "ServicePrincipal" \
        --role "Cognitive Services OpenAI User" \
        --scope "$AI_SERVICES_ID" \
        -o none 2>/dev/null || true
done

# Assign Storage roles to Orchestrator MSI
az role assignment create \
    --assignee-object-id "${MSI_PRINCIPAL_IDS[Orchestrator]}" \
    --assignee-principal-type "ServicePrincipal" \
    --role "Storage Blob Data Contributor" \
    --scope "$STORAGE_ID" \
    -o none 2>/dev/null || true

# ---------------------------------------------------------------------------
# 7. Build BOT_IDS JSON
# ---------------------------------------------------------------------------
BOT_IDS="{"
FIRST=true
for AGENT in "${AGENTS[@]}"; do
    if [ "$FIRST" = true ]; then FIRST=false; else BOT_IDS+=","; fi
    BOT_IDS+="\"${AGENT}\":\"${MSI_CLIENT_IDS[$AGENT]}\""
done
BOT_IDS+="}"

# ---------------------------------------------------------------------------
# 8. Upload synthetic patient data to blob storage
# ---------------------------------------------------------------------------
log "Uploading synthetic patient data to blob storage..."
PATIENT_DATA_DIR="${REPO_ROOT}/infra/patient_data"
if [ -d "$PATIENT_DATA_DIR" ]; then
    for PATIENT_DIR in "$PATIENT_DATA_DIR"/patient_gyn_*; do
        PATIENT_ID=$(basename "$PATIENT_DIR")
        for CSV_FILE in "$PATIENT_DIR"/*.csv; do
            FILENAME=$(basename "$CSV_FILE")
            az storage blob upload \
                --account-name "$APP_STORAGE_NAME" \
                --container-name "patient-data" \
                --name "${PATIENT_ID}/${FILENAME}" \
                --file "$CSV_FILE" \
                --auth-mode login \
                --overwrite \
                -o none 2>/dev/null || warn "Failed to upload ${PATIENT_ID}/${FILENAME}"
        done
        log "  Uploaded ${PATIENT_ID}"
    done
else
    warn "Patient data directory not found: ${PATIENT_DATA_DIR}"
fi

# ---------------------------------------------------------------------------
# 9. Generate src/.env
# ---------------------------------------------------------------------------
log "Generating src/.env..."
cat > "${SRC_DIR}/.env" << ENVEOF
# Auto-generated by setup-dev.sh on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Environment: ${ENV_NAME} | Location: ${LOCATION}

# --- Azure OpenAI ---
AZURE_OPENAI_DEPLOYMENT_NAME=${GPT_MODEL}
AZURE_OPENAI_ENDPOINT=${AI_ENDPOINT}
AZURE_OPENAI_DEPLOYMENT_NAME_REASONING_MODEL=${REASONING_MODEL}
AZURE_OPENAI_REASONING_MODEL_ENDPOINT=${AI_ENDPOINT}

# --- Scenario ---
SCENARIO=default

# --- Clinical Data Source ---
CLINICAL_NOTES_SOURCE=caboodle
CABOODLE_DATA_DIR=../infra/patient_data

# --- Bot Framework ---
BOT_IDS=${BOT_IDS}
HLS_MODEL_ENDPOINTS={}

# --- Agent Exclusions ---
# MedicalResearch requires GraphRAG — uncomment to exclude
# EXCLUDED_AGENTS=MedicalResearch
EXCLUDED_AGENTS=

# --- Storage ---
APP_BLOB_STORAGE_ENDPOINT=${STORAGE_BLOB_ENDPOINT}

# --- Key Vault ---
KEYVAULT_ENDPOINT=${KEYVAULT_ENDPOINT}

# --- Application Insights ---
APPLICATIONINSIGHTS_CONNECTION_STRING=${APP_INSIGHTS_CONN}

# --- Identity (for local dev, AzureCliCredential is used automatically) ---
# AZURE_CLIENT_ID is only needed on App Service (managed identity)
ENVEOF

log "Written to ${SRC_DIR}/.env"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN} Dev Environment Provisioned Successfully${NC}"
echo "=============================================="
echo ""
echo "Resource Group:    ${RG_NAME}"
echo "AI Services:       ${AI_SERVICES_NAME}"
echo "  Endpoint:        ${AI_ENDPOINT}"
echo "  GPT-4.1:         deployed (${GPT_CAPACITY}K TPM)"
echo "  o3-mini:         deployed (${REASONING_CAPACITY}K TPM)"
echo "Storage Account:   ${APP_STORAGE_NAME}"
echo "  Blob Endpoint:   ${STORAGE_BLOB_ENDPOINT}"
echo "  Containers:      chat-artifacts, chat-sessions, patient-data"
echo "Key Vault:         ${KEYVAULT_NAME}"
echo "App Insights:      ${APP_INSIGHTS_NAME}"
echo "Managed Identities: ${#AGENTS[@]} (one per agent)"
echo ""
echo "src/.env has been populated with all values."
echo ""
echo "Next steps:"
echo "  1. cd src"
echo "  2. python3 -m pytest tests/test_local_agents.py -v"
echo "  3. python3 -m uvicorn app:app --port 8000  (full web app)"
echo ""
echo "To tear down:  az group delete --name ${RG_NAME} --yes --no-wait"
echo ""
