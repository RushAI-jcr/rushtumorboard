# Rush GYN Oncology Tumor Board — Agent Orchestrator

A multi-agent system that coordinates specialized AI agents to support **Gynecologic Oncology Tumor Board** case reviews at Rush University Medical Center. Built on Microsoft Semantic Kernel, the system extracts, structures, and presents patient data from Epic Clarity/Caboodle in clinical shorthand format.

> [!IMPORTANT]
> This system is intended for research and development use only. It is not designed for clinical deployment as-is and has not been validated for diagnosis or treatment decisions. Users bear sole responsibility for verifying outputs, compliance with healthcare regulations, and obtaining necessary approvals.

## Features

- **10 specialized agents** collaborating via Semantic Kernel group chat
- **GYN oncology-focused** extraction: pathology, radiology, tumor markers, oncologic history
- **Outside hospital (OSH) transfer support** — structured history extraction for the ~20-30% of patients referred from other institutions
- **Landscape 4-column Word document** matching the current Rush tumor board format (Diagnosis & History | Previous Tx/Findings | Imaging | Discussion)
- **3-slide PowerPoint** summary with CA-125 trend chart
- **Clinical trials search** via NCI ClinicalTrials.gov API
- **GraphRAG-powered** medical research retrieval
- Integration with Microsoft Teams and Copilot Studio via MCP

## Solution Architecture
![Solution Architecture](media/architecture.png)

Agents are defined in `agents.yaml` and orchestrated through Semantic Kernel's group chat. Each agent has access to specialized tools (SK plugins). The Orchestrator facilitates the tumor board discussion flow, calling on each agent in sequence.

## AI Agent Role Summaries

| Agent | Role |
|-------|------|
| **Orchestrator** | Facilitates tumor board discussion, manages agent turn order (steps a–i) |
| **PatientHistory** | Loads patient record from Epic Caboodle, builds chronological timeline |
| **OncologicHistory** | Extracts structured prior oncologic history from clinical notes — diagnosis, treatments, recurrences, reason for referral. Critical for OSH transfers |
| **Pathology** | Extracts histology, IHC stains, molecular markers, FIGO grade, molecular classification |
| **Radiology** | Structures imaging findings from CT, MRI, PET/CT, ultrasound reports |
| **PatientStatus** | Synthesizes current status: FIGO staging, molecular profile, treatment history, platinum sensitivity |
| **ClinicalGuidelines** | Generates NCCN-based treatment recommendations for GYN cancers |
| **ClinicalTrials** | Searches NCI ClinicalTrials.gov for eligible trials with GOG/NRG awareness |
| **MedicalResearch** | Retrieves research-backed insights using Microsoft GraphRAG |
| **ReportCreation** | Assembles landscape 4-column Word doc + 3-slide PPTX for tumor board |

## Getting Started

### Prerequisites

- An Azure subscription with:
    - Azure OpenAI: 100k Tokens per Minute of Pay-as-you-go quota for GPT-4o or GPT-4.1
    - Optionally access to a reasoner model such as GPT-o3-mini
    - Azure App Services: Available VM quota - P1mv3 recommended
    - A resource group where you have _Owner_ permissions
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-linux)
- Python 3.12 or later (for running locally)
- Epic Clarity/Caboodle access (for production patient data)

### Step 1: Verify Prerequisites (Quota & Permissions)

Before deploying, verify your Azure subscription has sufficient quota.

**Resource Requirements:**

* **Azure OpenAI Quota**
  - Ensure you have quota for either **GPT-4o** or **GPT-4.1** models (`GlobalStandard`) in your `AZURE_GPT_LOCATION` region (recommended: 100K-200K TPM)

* **App Service Capacity**
  - Verify App Service quota in your `AZURE_APPSERVICE_LOCATION` region
  - Ensure sufficient capacity for P1mv3 App Service Plan

**Required Permissions:**

* **Azure Resource Access**
  - You need **Owner** rights on at least one resource group

* **Teams Integration**
  - Ensure your IT admin allows custom Teams apps to be uploaded—see [Teams app upload](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/deploy-and-publish/apps-upload)


### Step 2: Create an `azd` Environment & Set Variables

```sh
# Log in to Azure CLI and Azure Developer CLI
az login                 # add -t <TENANT_ID> if needed
azd auth login           # add --tenant <TENANT_ID> if needed
```

Create a new environment:
```sh
azd env new <envName>
```

Configure region settings (only set values that differ from your main `AZURE_LOCATION`):

```sh
azd env set AZURE_GPT_LOCATION <gpt-region>
azd env set AZURE_APPSERVICE_LOCATION <region>
```

| Variable | Purpose | Default Value |
|----------|---------|---------------|
| AZURE_LOCATION | Primary location for all resources | Defaults to resource group region |
| AZURE_GPT_LOCATION | Region for GPT resources | Defaults to `AZURE_LOCATION` |
| AZURE_APPSERVICE_LOCATION | Region for App Service deployment | Defaults to `AZURE_LOCATION` |
| CLINICAL_NOTES_SOURCE | Source of clinical notes. Accepted: `blob`, `fhir`, `fabric` | Defaults to `blob` |

[OPTIONAL] Configure FHIR data access for Epic integration:

```sh
azd env set CLINICAL_NOTES_SOURCE fhir
```

> [!NOTE]
> To set up the research agent with GraphRAG, see the [User Guide](./docs/user_guide.md#configuring-research-agent)

### Step 3: Deploy the Infrastructure

> [!IMPORTANT]
> Deploying will create Azure resources and may incur costs.

```bash
azd up
```

During deployment you will be prompted for subscription, region, and resource group. Pick **User** as the principal type.

> [!TIP]
> For persistent issues, use `azd down --purge` to reset.

> [!IMPORTANT]
> Full deployment can take 20-30 minutes. See the [Troubleshooting guide](./docs/troubleshooting.md) for common issues.

### Step 4: Install Agents in Microsoft Teams

```sh
./scripts/uploadPackage.sh ./output <teamsChatId|meetingLink> [tenantId]
```

See [Teams documentation](./docs/teams.md) for details on finding chat IDs and managing agent permissions.

### Step 5: Test the Agents

```
@Orchestrator clear                  # Reset conversation state
```

Start a GYN tumor board review:
```
@Orchestrator Can you start a tumor board review for Patient ID: patient_gyn_001?
```

Interact with specific agents:
```
@PatientHistory create patient timeline for patient id patient_gyn_001
@OncologicHistory extract oncologic history for patient_gyn_001
@Pathology extract pathology findings for patient_gyn_001
```

See the [User Guide](./docs/user_guide.md) for detailed testing instructions.

### Step 6: Using the React Client Application

A chat UI is deployed alongside the backend. Access it using the URL from `azd up` output.

> [!NOTE]
> By default the app is only accessible from Microsoft 365/Teams IP ranges. Add your IP for direct access:
> ```sh
> azd env set ADDITIONAL_ALLOWED_IPS "your.ip.address/32"
> azd up
> ```

### [Optional] Uninstall / Clean-up

```sh
azd down --purge
```

## Tumor Board Output Format

### Word Document (Landscape 4-Column)
The ReportCreation agent generates a one-page landscape Word document with:

| Column 1 | Column 2 | Column 3 | Column 4 |
|-----------|----------|----------|----------|
| Diagnosis & Pertinent History | Previous Tx or Operative Findings, Tumor Markers | Imaging | Discussion |

Content uses clinical shorthand (s/p, dx, bx, LN, OSH, c/w) with M/D/YY date format.

### PowerPoint (3 Slides)
1. **Overview** — patient demographics, diagnosis, staging
2. **Findings** — pathology, imaging, CA-125 trend chart
3. **Treatment Plan** — recommendations, eligible clinical trials

## Resources

### Project Documentation

- [User Guide](./docs/user_guide.md) and [Documentation Index](docs/README.md)
- [Agent Development Guide](./docs/agent_development.md) for building and customizing agents
- [Tool Integration Guide](./docs/agent_development.md#adding-tools-plugins-to-your-agents)
- [GYN Tumor Board Scenario Guide](./docs/scenarios.md)
- [Data Access & Epic Integration](./docs/data_access.md)
- [Data Ingestion Guide](./docs/data_ingestion.md) for adding patient data
- [MCP & Copilot Integration](./docs/mcp.md)
- [Network Architecture](./docs/network.md)
- [Teams Integration Guide](./docs/teams.md)

### External Documentation

- [Introduction to Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/overview/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/overview)
- [NCCN Guidelines — Gynecologic Cancers](https://www.nccn.org/guidelines/category_1)
- [NCI ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/about-api)

## Guidance

Deployment creates:
- 1 [GPT-4o deployment](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)
- 1 [App Service](https://learn.microsoft.com/en-us/azure/app-service/overview)
- 2 [Azure Storage accounts](https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview)
- Associated [managed identities](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview) and [Azure Bot](https://learn.microsoft.com/en-us/azure/bot-service/bot-service-overview?view=azure-bot-service-4.0) instances

### Security

All resources use Entra ID authentication. No passwords are stored. The web app exposes a public unauthenticated endpoint — files under `infra/patient_data` will be publicly available.

## Ethical Considerations
Microsoft believes Responsible AI is a shared responsibility. While testing agents with patient data, ensure the data contains no PHI/PII and cannot be traced to a patient identity. Please see [Microsoft's Responsible AI Principles](https://www.microsoft.com/en-us/ai/principles-and-approach/).

## Contact Us

For questions or inquiries, please contact the Rush AI team.

### Issues and Support

If you encounter issues, please create a [GitHub issue](https://github.com/RushAI-jcr/rushtumorboard/issues) with details and reproduction steps.
