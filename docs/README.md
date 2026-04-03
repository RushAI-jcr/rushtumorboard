# Documentation — Rush GYN Oncology Tumor Board

Consult the main [README](../README.md) for project overview and getting started.

## General Documentation
- [User Guide](./user_guide.md): Using the GYN tumor board agents and reviewing outputs
- [Microsoft Teams](./teams.md): Setting up Teams integration for tumor board collaboration
- [Data Ingestion](./data_ingestion.md): How to import and process GYN oncology patient data
- [Data Access & Epic Integration](./data_access.md): Data access layer, accessor protocol, and 3-layer note fallback
- [FHIR Integration](./fhir_integration.md): Azure Health Data Services FHIR server integration
- [Fabric Integration](./fabric/fabric_integration.md): Microsoft Fabric clinical note function
- [Evaluation](./evaluation.md): Methods for measuring agent performance
- [Infrastructure](./infra.md): Deployment infrastructure and SSO configuration
- [Network Architecture](./network.md): Network configuration and security
- [Access Control](./access_control.md): Restricting access to deployed agents

## Developer Documentation
- [Agent Development](./agent_development.md): Creating and customizing GYN tumor board agents
- [Scenarios](./scenarios.md): GYN tumor board scenario structure and configuration
- [MCP & Copilot Integration](./mcp.md): MCP server and Copilot Studio integration

## Issues
- [Troubleshooting](./troubleshooting.md): Common problems and solutions
- [Debugging](./debugging.md): Logging configuration and diagnostic tools
- [FAQ](./faq.md): Frequently asked questions

## Solutions & Learnings
- [Multi-Layer Fallback & CSV Caching](./solutions/data-issues/multi-layer-fallback-csv-caching-strategy.md)
- [GYN Tumor Board Adaptation](./solutions/integration-issues/gyn-tumor-board-adaptation.md)
- [NCCN Guidelines Agent Integration](./solutions/integration-issues/nccn-guidelines-agent-integration.md)
- [Batch E2E Validation (15 Patients)](./solutions/integration-issues/batch-e2e-validation-15-patients.md)
- [CA-125 Chart PPTX Type Guard](./solutions/logic-errors/ca125-chart-missing-pptx-type-guard-dict.md)
