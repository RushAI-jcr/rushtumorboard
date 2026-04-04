---
title: "Multi-Agent Code Review: Tiered Data Source Architecture"
date: 2026-04-04
category: code-review
problem_type: systematic-audit
severity:
  p1: 3
  p2: 12
  p3: 5
  total: 20
tags:
  - semantic-kernel
  - azure-openai
  - gyn-oncology
  - tumor-board
  - mcp
  - graphrag
  - phi-scrubbing
  - timeout-safety
  - message-enrichment
  - code-quality
  - security
  - reliability
components:
  - src/scenarios/default/tools/oncologic_history_extractor.py
  - src/scenarios/default/tools/pretumor_board_checklist.py
  - src/scenarios/default/tools/clinical_trials.py
  - src/scenarios/default/tools/tumor_markers.py
  - src/scenarios/default/tools/graph_rag.py
  - src/scenarios/default/tools/note_type_constants.py
  - src/utils/message_enrichment.py
  - src/utils/phi_scrubber.py
  - src/mcp_app.py
  - src/routes/api/chats.py
  - src/scenarios/default/config/agents.yaml
symptoms:
  - indefinite-blocking-on-llm-call
  - missing-message-enrichment-in-mcp-channel
  - phi-leak-via-graphrag-api
  - type-annotation-gaps
  - inline-imports-in-hot-paths
  - unused-dead-code
  - invalid-html-in-output
  - redos-vulnerable-regex
  - unvalidated-urls
  - unbounded-structured-data
  - stale-config-drift
  - hardcoded-function-signatures
---

# Multi-Agent Code Review: Tiered Data Source Architecture

A comprehensive multi-agent code review of the rushtumorboard GYN Oncology Tumor Board system identified 20 issues across the tiered data source architecture. All 20 were fixed in a single session. This document captures the root causes, solutions, bug patterns, and prevention strategies.

## Root Cause Analysis

The 20 issues fell into three systemic categories:

1. **Extraction drift (P1s):** When functionality was refactored and centralized (PHI scrubbing to `utils/phi_scrubber.py`, message enrichment to `utils/message_enrichment.py`, LLM timeout to `medical_report_extractor.py`), not all call sites were updated. The subclass `oncologic_history_extractor.py` overrode `_extract()` and duplicated the LLM call pattern but missed the `asyncio.wait_for()` timeout wrapper. The MCP response path in `mcp_app.py` was missed when enrichment was extracted. The GraphRAG external API call was missed when PHI scrubbing was centralized.

2. **Incremental feature accumulation (P2s):** As tools grew organically (tumor_markers adding 6 inline normalization chains, oncologic_history_extractor adding structured preamble without a size cap, medications serialized without filtering), technical debt accumulated without a consolidation pass.

3. **Stale artifacts (P3s):** Dead code branches, unused config files, and pre-Python-3.10 typing imports remained from the upstream Microsoft fork and earlier refactors.

## Investigation Approach

Seven parallel analysis agents examined the full `src/` tree:

| Agent | Focus |
|-------|-------|
| security-sentinel | PHI leakage, input validation, OWASP |
| performance-oracle | Timeouts, unbounded data, ReDoS |
| architecture-strategist | Tier design, parity, coupling |
| kieran-python-reviewer | Type safety, Pythonic patterns, dead code |
| code-simplicity-reviewer | DRY violations, unnecessary complexity |
| agent-native-reviewer | Agent/tool parity, prompt drift |
| learnings-researcher | Cross-reference with past solutions |

Findings were deduplicated and prioritized: P1 = production failure or data leak, P2 = correctness or maintainability, P3 = style or dead code.

---

## P1 Solutions (Critical)

### #172 -- LLM timeout missing in oncologic_history_extractor.py

**Root cause:** `_extract()` override duplicated the base class LLM call but omitted the `asyncio.wait_for()` timeout wrapper that `medical_report_extractor.py` uses with `_LLM_TIMEOUT_SECS = 90.0`. Oncologic history extractions could hang indefinitely if the Azure OpenAI endpoint stalled.

**Fix:**

```python
from .medical_report_extractor import MedicalReportExtractorBase, _JSON_FENCE_RE, _LLM_TIMEOUT_SECS

try:
    chat_resp = await asyncio.wait_for(
        chat_completion_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        ),
        timeout=_LLM_TIMEOUT_SECS,
    )
except asyncio.TimeoutError:
    logger.warning(
        "LLM oncologic history extraction timed out after %.0fs for patient %s",
        _LLM_TIMEOUT_SECS, patient_id,
    )
    return json.dumps({
        "patient_id": patient_id,
        "error": "LLM oncologic history extraction timed out.",
        self.error_key: []
    })
```

### #173 -- MCP enrichment gap in mcp_app.py

**Root cause:** Message enrichment (patient image tags, clinical trial links, SAS-signed blob URLs) was extracted to `utils/message_enrichment.py` but only applied in Teams bot and WebSocket handlers. The MCP/Copilot Studio path was missed.

**Fix:**

```python
from utils.message_enrichment import append_links, apply_sas_urls

async for response in chat.invoke(agent=agent):
    content = append_links(response.content, chat_ctx)
    content = await apply_sas_urls(content, chat_ctx, data_access)
    responses.append({"name": response.name, "content": content})
```

### #174 -- PHI scrubbing gap in graph_rag.py

**Root cause:** During centralization of PHI scrubbing, the GraphRAG external API call was missed. Patient-identifying information (MRNs, dates, names) could leak to the external endpoint.

**Fix:**

```python
from utils.phi_scrubber import scrub_phi

prompt = scrub_phi(prompt)  # Before building the GraphRAG request body
```

---

## P2 Solutions (12 Fixes)

| # | Issue | File(s) | Fix |
|---|-------|---------|-----|
| 175 | Missing type annotations | `pretumor_board_checklist.py`, `message_enrichment.py` | Added `DataAccess`, `ChatContext`, `ClinicalNoteAccessorProtocol` types |
| 176 | Inline imports in methods | `pretumor_board_checklist.py` | Moved `import asyncio` and `note_type_constants` to top-level |
| 177 | Dead `_get_diagnoses` method | `pretumor_board_checklist.py` | Removed from `asyncio.gather` destructuring and deleted method |
| 178 | `<li>` without `<ul>` | `message_enrichment.py` | Wrapped in `<ul></ul>` tags |
| 179 | ReDoS in PHI scrubber | `phi_scrubber.py` | Changed `(?:T\S+)?` to `(?:T\S{1,30})?` |
| 180 | URL uses unvalidated variable | `clinical_trials.py` | Changed `+ trial` to `+ nct_id` |
| 181 | Unbounded structured preamble | `oncologic_history_extractor.py` | Added `MAX_STRUCTURED_CHARS = 30_000`, compact JSON, truncation guard |
| 182 | 6 duplicated normalization chains | `tumor_markers.py` | Created `_normalize_marker()` helper; fixed missing `.replace(" ", "")` bug |
| 183 | Sequential 2-tier imaging fallback | `pretumor_board_checklist.py` | Collapsed into single `get_clinical_notes_by_keywords` with combined types |
| 184 | Stale config file | `healthcare_agents.yaml` | Deleted (not loaded by config, misleading) |
| 185 | Misleading prompt wording | `agents.yaml` | Clarified pathology_reports.csv accessed via tumor markers tool |
| 186 | Unfiltered medications | `oncologic_history_extractor.py` | Added `_ONCOLOGY_MED_CLASSES` filter before serializing to LLM |

---

## P3 Solutions (5 Fixes)

| # | Issue | File(s) | Fix |
|---|-------|---------|-----|
| 187 | Repetitive if/append blocks | `oncologic_history_extractor.py` | Replaced with `for label, data in [...]` loop |
| 188 | Undocumented tier overlap | `note_type_constants.py` | Added comment explaining intentional Tier A/B overlap |
| 189 | Dead `BaseException` branch | `clinical_trials.py` | Removed unreachable branch |
| 190 | Legacy typing imports | `chats.py` | `Dict/List/Optional` to `dict/list/X \| None` |
| 191 | Hardcoded function signatures | `agents.yaml` | Replaced with role-based delegation language |

---

## Bug Patterns and Prevention Strategies

### Pattern 1: Feature parity gaps when extracting shared code (#173, #174)

When a capability is centralized into a shared module, adoption is verified manually and call sites get missed.

**Prevention:**
- After any extraction refactor, grep the entire codebase for the old inline implementation
- Maintain a consumer list at the top of shared modules (Teams bot, WebSocket, MCP)
- Parametrized integration test across all delivery channels asserting enrichment is present
- Semgrep rule: if shared function X exists, no other file should contain the raw pattern inline

### Pattern 2: Override methods missing base class safety patterns (#172)

Python does not enforce that a subclass override reproduces the safety wrappers of the base class.

**Prevention:**
- **Template Method pattern:** Base class owns the safety wrapper and calls an abstract hook:
  ```python
  async def extract(self):  # Do not override
      return await asyncio.wait_for(self._do_extract(), timeout=self._timeout)

  @abstractmethod
  async def _do_extract(self): ...  # Subclasses override only this
  ```
- Mark wrapper methods with `@typing.final` so type checkers flag overrides
- Timeout enforcement test: for every extractor subclass, mock the data source to hang and assert TimeoutError within `timeout + 1s`

### Pattern 3: Incomplete string normalization (#182)

Normalization logic copy-pasted as inline method chains across 6+ call sites. When normalization evolves, some sites are missed.

**Prevention:**
- Single `_normalize_marker()` function; the chain never appears inline
- Semgrep rule flagging `.lower().replace("-", "")` chains outside the canonical utility
- Parametrized equivalence test: `("CA 125", "CA-125", "ca125")` all normalize to the same value

### Pattern 4: Unbounded regex in security-sensitive code (#179)

The PHI scrubber used `\S+` (greedy, unbounded) in a pattern susceptible to ReDoS.

**Prevention:**
- Bounded quantifiers as coding standard in security modules (`\S{1,30}` not `\S+`)
- Integrate `regexploit` (ReDoS detection) into CI pipeline
- ReDoS fuzzing test: crafted long strings must complete within 100ms

### Pattern 5: Dead code / stale config accumulation (#177, #184, #189)

Code and config that is no longer exercised persists because nothing validates it.

**Prevention:**
- `ruff check --select F841,B018,F401` catches unused variables, expressions, imports
- `vulture` in CI for dead code detection
- Config round-trip test: load YAML, validate against Pydantic schema, assert all fields consumed

### Pattern 6: Inconsistent code style (#176, #190)

Legacy typing imports and inline imports persist without automated enforcement.

**Prevention:**
- Enable `ruff` rules `UP006`, `UP007`, `UP035` (modern typing), `E402` (top-level imports)
- One-time sweep: `ruff check --fix --select UP006,UP007,UP035,E402` across codebase

---

## Review Checklist

For future code reviews on this codebase:

1. **Extraction refactors:** Are ALL consumers migrated? Grep for the old pattern.
2. **Subclass overrides:** Does the subclass override only the intended hook? Is the safety wrapper in the base class?
3. **String normalization:** Is comparison logic using the canonical utility, not an inline chain?
4. **Regex in security code:** Are all quantifiers bounded? Has `regexploit` been run?
5. **Dead code:** Does `vulture` pass? Are all fetched results used?
6. **Style consistency:** Does `ruff` pass with the full rule set?

---

## Cross-References

- [PHI Leakage & External APIs](../security-issues/phi-leakage-external-apis-hipaa-compliance.md) -- PHI scrubber, message enrichment, prompt hardening
- [Multi-Layer Fallback & CSV Caching](../data-issues/multi-layer-fallback-csv-caching-strategy.md) -- Tier A/B/C design, caching, volume caps
- [CA-125 Chart Type Guard](../logic-errors/ca125-chart-missing-pptx-type-guard-dict.md) -- Marker normalization, type guards
- [GYN Tumor Board Adaptation](../integration-issues/gyn-tumor-board-adaptation.md) -- Agent architecture, Epic accessor
- [Data Access Layer](../../data_access.md) -- ClinicalNoteAccessorProtocol, CaboodleFileAccessor
- [Agent Development Guide](../../agent_development.md) -- Agent YAML config, tool discovery
- Todo files: `todos/172-complete-p1-*` through `todos/191-complete-p3-*` (20 files)
