---
review_agents:
  - compound-engineering:review:security-sentinel
  - compound-engineering:review:performance-oracle
  - compound-engineering:review:architecture-strategist
  - compound-engineering:review:kieran-python-reviewer
  - compound-engineering:review:code-simplicity-reviewer
---

## Project Review Context

This is a GYN Oncology Tumor Board multi-agent system at Rush University Medical Center, forked from Microsoft healthcare-agent-orchestrator. Key context for reviewers:

- Python 3.12+, Semantic Kernel, Azure OpenAI GPT-4o
- Handles real patient PHI — HIPAA compliance is critical; no PHI in code, logs, or version control
- Epic Caboodle CSV data access with 3-layer fallback (dedicated CSV → domain NoteTypes → keyword-filtered notes)
- Multi-agent system: 10 Semantic Kernel agents each with LLM calls; context window overflow is a real risk
- Async throughout (asyncio); session-scoped in-memory cache for CSV files
- `infra/patient_data/` contains real patient data (gitignored); only synthetic patients in version control
