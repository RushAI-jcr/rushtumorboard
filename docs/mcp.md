# MCP Integration — GYN Oncology Tumor Board

## Overview of MCP

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol for seamless integration between agents and tools. In this project, MCP is used in two ways:

1. **Orchestrator MCP Server** — exposes all tumor board agents as tools via MCP, allowing external clients (like Copilot Studio) to interact with the system
2. **Clinical Trials MCP Server** — a FastMCP server at `/clinical-trials/` that provides NCI ClinicalTrials.gov search capabilities

## Orchestrator MCP Server

### Implementation
The MCP implementation resides in `./src/mcp_app.py`. A route is exposed under `/mcp/orchestrator`, where each of the 10 GYN tumor board agents is treated as an individual tool. Each MCP session creates a new group chat with shared history and context. Uses [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http) for stateless session management.

### Available Agent Tools via MCP
| Tool | Description |
|------|-------------|
| Orchestrator | Facilitates tumor board discussion |
| PatientHistory | Loads patient record, builds timeline |
| OncologicHistory | Extracts prior oncologic history from clinical notes |
| Pathology | Extracts pathology findings |
| Radiology | Structures imaging findings |
| PatientStatus | Synthesizes current clinical status |
| ClinicalGuidelines | NCCN-based GYN treatment recommendations |
| ClinicalTrials | Searches for eligible clinical trials |
| MedicalResearch | PubMed/Europe PMC/Semantic Scholar search with RISEN synthesis |
| ReportCreation | Generates Word doc + PPTX |

## Clinical Trials MCP Server

A dedicated FastMCP server provides clinical trial search capabilities using the NCI ClinicalTrials.gov API. Located at `/clinical-trials/`, it enables agents to search for GYN oncology trials with awareness of GOG/NRG cooperative group trials.

## Copilot Studio Integration

Copilot Studio supports MCP through its connector interface. This enables full integration with the M365 ecosystem with enterprise security controls like [Virtual Networks](https://learn.microsoft.com/en-us/power-platform/admin/vnet-support-overview) and [Data Loss Prevention](https://learn.microsoft.com/en-us/power-platform/admin/wp-data-loss-prevention).

### Creating a Custom MCP Connector

Follow: [Create a Custom MCP Connector](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-mcp)

Use the following Swagger definition, replacing `REPLACE_ME` with your deployed hostname:

```sh
azd env get-value BACKEND_APP_HOSTNAME
```

```yaml
swagger: '2.0'
info:
  title: MCP server Rush GYN Tumor Board
  description: >-
    GYN oncology tumor board agents. Provides patient history, oncologic history,
    pathology, radiology, clinical guidelines, trials, and report generation.
  version: 1.0.0
host: REPLACE_ME
basePath: /mcp
schemes:
  - https
consumes: []
produces: []
paths:
  /orchestrator/:
    post:
      summary: MCP server Rush GYN Tumor Board
      parameters:
        - in: body
          name: queryRequest
          schema:
            $ref: '#/definitions/QueryRequest'
        - in: header
          name: Mcp-Session-Id
          type: string
          required: false
      produces:
        - application/json
      responses:
        '200':
          description: Immediate Response
          schema:
            $ref: '#/definitions/QueryResponse'
        '201':
          description: Created and will follow callback
      operationId: InvokeMCP
      tags:
        - Agentic
        - McpStreamable
definitions:
  QueryRequest:
    type: object
    properties:
      jsonrpc:
        type: string
      id:
        type: string
      method:
        type: string
      params:
        type: object
      result:
        type: object
      error:
        type: object
  QueryResponse:
    type: object
    properties:
      jsonrpc:
        type: string
      id:
        type: string
      method:
        type: string
      params:
        type: object
      result:
        type: object
      error:
        type: object
parameters: {}
responses: {}
securityDefinitions: {}
security: []
tags: []
```

Follow the [documentation](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-mcp#create-a-custom-mcp-connector) to complete connector setup.

### Creating a Copilot Agent

After creating the connector, create an agent that consumes the MCP server:
[Add an Existing MCP Action to an Agent](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-mcp#add-an-existing-mcp-action-to-an-agent)

Use these instructions for your Copilot agent:

> You are overseeing a group chat between several AI agents and a human user. Each AI agent can be invoked through the use of a tool.
> For any action, question, or statement by the user, always start by invoking the orchestrator agent. The orchestrator agent will create a general plan. You can then execute the plan by invoking each agent in sequence.
> Reason deeply about the plan and how to best execute it. Return the results of each action without modifications, ensuring links are preserved. Return results as soon as they are available, if possible.
> Continue executing actions in sequence until the user query is resolved.

Enable [Generative Orchestration](https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-generative-actions) for automatic tool discovery.

Under "Tools," select "Add Tool" and choose the MCP connector (`MCP Server Rush GYN Tumor Board`).

Test your changes and publish your agent.
