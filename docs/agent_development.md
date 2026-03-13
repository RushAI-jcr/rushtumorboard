# Agent Development Guide
Everything you need to define new agents and give them custom tools for the GYN Oncology Tumor Board.

## Table of Contents
- [Create / Modify Agents](#create--modify-agents)
- [Deploy Changes](#deploy-changes)
- [Adding tools (plugins) to your agents](#adding-tools-plugins-to-your-agents)

## Create / Modify Agents

### Adding a New Agent
1. Open your scenario's `src/<SCENARIO>/config/agents.yaml` file
2. Add a new entry with the hyphen prefix `-` to create a new agent in the list. Agent names should be limited to alphanumerical characters. Avoid dashes or whitespace.
3. Include all required fields and any optional fields you need
4. Save the file

### Required YAML Fields
| Field | Purpose |
|-------|---------|
| **name** | Unique identifier for the agent |
| **instructions** | System prompt the LLM receives |
| **description** | Brief text used in UI blurb and by orchestrator to determine when/how to use the agent |

### Optional Fields
| Field | Purpose |
|-------|---------|
| **tools** | List of Semantic-Kernel plugin names the agent can call. See [tools](#adding-tools-plugins-to-your-agents) |
| **temperature** | LLM temperature (defaults to `0`) |
| **facilitator** | `true` → this agent moderates the conversation (only **one** allowed) |
| Other model parameters | e.g., `graph_rag_url`, `graph_rag_index_name`, `top_p`, `max_tokens` |

### Example Agent
```yaml
- name: OncologicHistory
  instructions: |
    You are **OncologicHistory**. Extract and present prior oncologic history
    in clinical shorthand (s/p, dx, bx, LN, OSH, etc.) using dates as M/D/YY.
    Use `extract_oncologic_history` tool. Present: opening line, staging block,
    chronological cancer history (-date: event), current status, and reason
    for referral. Flag OSH vs Rush events.
    Yield back with "back to you: *Orchestrator*".
  temperature: 0
  tools:
    - name: oncologic_history_extractor
    - name: patient_data
  description: |
    An oncologic history agent for GYN tumor board. **You provide**: structured
    prior oncologic history including diagnosis timeline, treatments received,
    recurrences, molecular profile, current status, and reason for referral.
    **You need**: patient data loaded by PatientHistory.
```

### Add a Custom Icon (Optional)
1. Place the PNG/SVG in `infra/botIcons/`
2. Reference it inside `infra/modules/botservice.bicep`


## Deploy Changes

1. Save your updated YAML and plugin code.
2. Run the standard deployment:
```bash
azd up
```
3. Install/refresh the Teams app package if new agents or icons were added:
```bash
uploadPackage.sh ./output <chatId|meetingLink> [tenantId]
```

## Adding tools (plugins) to your agents

### Understanding Tools and Function Calling

Tools are Semantic-Kernel **plugins** that extend your agent's capabilities. Function calling enables an agent to interact with external tools, APIs, or data in a controlled way. The framework automatically discovers any plugin that exposes a `create_plugin()` factory function.

For detailed information on SK plugins, see the [official documentation](https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/?pivots=programming-language-python).

### Provided Tools — GYN Tumor Board

| Plugin | Function |
|--------|----------|
| `content_export` | Export tumor board summary to landscape 4-column Word document |
| `presentation_export` | Export 3-slide PPTX with CA-125 trend chart |
| `oncologic_history_extractor` | Extract structured prior oncologic history from clinical notes |
| `pathology_extractor` | Extract pathology findings (histology, IHC, molecular markers) |
| `radiology_extractor` | Extract imaging findings from radiology reports |
| `tumor_markers` | Extract and trend tumor markers (CA-125, HE4, etc.) |
| `clinical_trials_nci` | Search NCI ClinicalTrials.gov for eligible GYN trials |
| `clinical_trials` | Search clinicaltrials.gov (legacy) |
| `graph_rag` | RAG search of research papers via GraphRAG |
| `patient_data` | Timeline + Q&A over patient notes from Epic Caboodle |


### Creating and Attaching Custom Tools

1. Create either:
  - Single file: `src/<SCENARIO>/tools/my_new_tool_plugin.py` with `create_plugin()` function
  - Package: `src/<SCENARIO>/tools/my_new_tool_plugin/__init__.py` with `create_plugin()` function + other files
  - OpenAPI: an OpenAPI specification. See the [OpenAPI Plugin Example](#agent-with-an-openapi-plugin-example) section.

The factory function must return your tool instance. The framework automatically discovers and loads tools referenced in agent configs.

2. Reference the tool in your agent configuration:

   ```yaml
   - name: <AgentName>
     tools:
       - name: <plugin_package>
         type: <function | openapi>
         openapi_document_path: <path or url (openapi only)>
         server_url_override: <url (openapi only)>
   ```

### Optimizing Agent Fields for Tool Integration

#### Instruction Field
Tell the agent explicitly WHEN to use its tool, explain WHY the tool exists, provide output handling guidance and end with a hand-off phrase.

**WHEN to use the tool:**
```yaml
Before proceeding, ensure you have the following information:
  patient_id (str): The patient ID to look up.
```

**WHY the tool exists:**
```yaml
# OncologicHistory agent:
* Use `extract_oncologic_history` to extract structured prior cancer history from clinical notes.
  This is especially valuable for OSH transfer patients.
```

**HOW to handle output:**
```yaml
# ClinicalTrials agent - format trial links:
Format the trial ID as [NCT123456](https://clinicaltrials.gov/study/NCT123456).
Present results with trial ID, title, and eligibility rationale.
```

**Hand-off:**
```yaml
- After replying, yield control: **"back to you: Orchestrator"**.
```

#### Description Field

The Orchestrator scans descriptions when deciding which agent to call, so clarity directly affects routing.

```yaml
# OncologicHistory - mentions what it provides and needs:
An oncologic history agent for GYN tumor board. **You provide**: structured
prior oncologic history. **You need**: patient data loaded by PatientHistory.
```

### Agent with a Tool Plugin Example

> src/<SCENARIO>/tools/weather_app.py:
```python

def create_plugin(plugin_config: PluginConfiguration) -> Kernel:
    return WeatherPlugin(plugin_config.kernel, plugin_config.chat_ctx)


class WeatherPlugin:
    def __init__(self, kernel: Kernel, chat_ctx: ChatContext):
        self.kernel = kernel
        self.chat_ctx = chat_ctx
        self.base_url = "https://wttr.in"

    @kernel_function()
    async def current_weather_zip(self, zip_code: str) -> str:
        url = f"{self.base_url}/{zip_code}?format=j1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                resp.raise_for_status()
                data = await resp.json()

        cur = data["current_condition"][0]
        return json.dumps(cur)
```

### Agent with an OpenAPI Plugin Example

> [!NOTE]
> The tool name passed to the LLM is a concatenation of the tool name in `agents.yaml` and the operation ID in the OpenAPI definition. Total length cannot exceed 64 characters.

```yaml
- name: PatientStatus
  instructions: |
    You are an AI agent that provides the patient's current status.
    If date of birth is available, calculate the age using the `time_plugin`.
  tools:
    - name: time_plugin
      type: openapi
      openapi_document_path: scenarios/default/config/openapi/time_api.yaml
      server_url_override: http://localhost:8000
  description: |
    A PatientStatus agent. **You provide**: current status. **You need**: staging, molecular profile, treatment history from PatientHistory.
```

#### OpenAPI Tool Configuration

```yaml
tools:
  - name: time_plugin
    type: openapi
    openapi_document_path: scenarios/default/config/openapi/time_api.yaml
    server_url_override: http://localhost:8000
    timeout: 600  # Optional: request timeout in seconds (default: 5)
    debug_logging: false  # Optional: enable debug logging (default: false)
```

## Next Steps

* [GYN Tumor Board Scenario Guide](./scenarios.md)
* [Data Access & Epic Integration](./data_access.md)
