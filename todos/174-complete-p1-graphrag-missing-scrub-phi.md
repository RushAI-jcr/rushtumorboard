---
status: pending
priority: p1
issue_id: "174"
tags: [code-review, security, phi, hipaa]
dependencies: []
---

# GraphRAG Plugin Missing PHI Scrubbing Before External API Call

## Problem Statement

`src/scenarios/default/tools/graph_rag.py` sends user prompts directly to an external GraphRAG endpoint (`self.graph_rag_url/query/local`) without calling `scrub_phi()`. While clinical_trials.py, medical_research.py, and clinical_trials_mcp.py all now scrub PHI before external calls, this tool was missed during the centralization effort.

## Findings

- **Source**: Security Sentinel (HIGH H-1)
- **File**: `src/scenarios/default/tools/graph_rag.py:56` — `prompt` parameter sent directly in request body without scrubbing
- **Comparison**: All other external API callers now use `from utils.phi_scrubber import scrub_phi`

## Proposed Solutions

### Option A: Add scrub_phi() call (Recommended)
```python
from utils.phi_scrubber import scrub_phi

# In process_prompt():
prompt = scrub_phi(prompt)
```

- **Pros**: One-line fix, consistent with all other external API calls
- **Effort**: Small (5 min)

## Acceptance Criteria

- [ ] `scrub_phi()` is called on the prompt before sending to the GraphRAG endpoint
- [ ] Import added at top of file
