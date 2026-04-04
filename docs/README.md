# Documentation — Rush GYN Oncology Tumor Board

See the main [README](../README.md) for project overview and getting started.

## Quick Links

| I want to... | Read this |
|--------------|-----------|
| Use the tumor board agents | [User Guide](./user_guide.md) |
| Set up local development | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Add or modify an agent | [Agent Development](./agent_development.md) |
| Understand the data layer | [Data Access](./data_access.md) |
| Import patient data | [Data Ingestion](./data_ingestion.md) |
| Deploy to Azure | [Infrastructure](./infra.md) |
| Troubleshoot an issue | [Troubleshooting](./troubleshooting.md) |

## User & Clinical Documentation

- [User Guide](./user_guide.md) — Using agents and reviewing tumor board outputs
- [Data Ingestion](./data_ingestion.md) — Importing and processing GYN oncology patient data
- [Evaluation](./evaluation.md) — Measuring agent performance and output quality

## Developer Documentation

- [Agent Development](./agent_development.md) — Creating and customizing agents
- [Scenarios](./scenarios.md) — Scenario structure and configuration
- [Data Access & Epic Integration](./data_access.md) — Data layer, accessor protocol, 3-layer note fallback
- [MCP & Copilot Integration](./mcp.md) — MCP server and Copilot Studio integration
- [Debugging](./debugging.md) — Logging configuration and diagnostic tools
- [FAQ](./faq.md) — Frequently asked questions

## Integration Guides

- [Microsoft Teams](./teams.md) — Teams integration and bot setup
- [FHIR Integration](./fhir_integration.md) — Azure Health Data Services
- [Fabric Integration](./fabric/fabric_integration.md) — Microsoft Fabric clinical note function

## Infrastructure & Operations

- [Infrastructure](./infra.md) — Deployment infrastructure and SSO
- [Network Architecture](./network.md) — Network configuration and security
- [Access Control](./access_control.md) — Restricting access to deployed agents
- [Contributor Provisioning](./contributor_provisioning.md) — Developer environment setup
- [Troubleshooting](./troubleshooting.md) — Common problems and solutions

## Architecture Decisions & Solutions

Plans, brainstorms, and solution writeups from development:

- **Plans**: [`docs/plans/`](./plans/) — Implementation plans for major features
- **Solutions**: [`docs/solutions/`](./solutions/) — Post-implementation learnings and patterns
- **Brainstorms**: [`docs/brainstorms/`](./brainstorms/) — Design exploration documents

### Key Solutions

- [Multi-Layer Fallback & CSV Caching](./solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md)
- [GYN Tumor Board Adaptation](./solutions/integration-issues/gyn-tumor-board-adaptation.md)
- [NCCN Guidelines Agent Integration](./solutions/integration-issues/nccn-guidelines-agent-integration.md)
- [Batch E2E Validation (15 Patients)](./solutions/integration-issues/batch-e2e-validation-15-patients.md)
- [CA-125 Chart PPTX Type Guard](./solutions/logic-errors/ca125-chart-missing-pptx-type-guard-dict.md)

## Open Issues

Active issues tracked in [`todos/`](../todos/):
```sh
ls todos/*-pending-*.md  # View all pending issues by priority
```
