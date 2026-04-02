---
title: ClinicalGuidelines Agent NCCN Tool Integration
date: 2026-04-02
category: integration-issues
tags:
  - agent-tools
  - pdf-parsing
  - knowledge-grounding
  - NCCN-guidelines
  - semantic-kernel
  - clinical-decision-support
severity: medium
component: ClinicalGuidelines Agent, NCCN Guidelines Tool
symptoms:
  - Agent provides treatment recommendations without citing specific NCCN page codes
  - No verifiable source material or grounding for guideline assertions
  - Risk of hallucinated or outdated guideline content
  - Agent unable to query structured guideline data at runtime
root_cause: ClinicalGuidelines agent had no tool access and relied entirely on LLM prompt instructions for NCCN knowledge
status: resolved
---

## Problem

The ClinicalGuidelines agent in the rushtumorboard GYN Oncology Tumor Board system was responsible for producing NCCN-based treatment recommendations but had **no tool access**. It relied entirely on hardcoded LLM prompt instructions.

**Symptoms:**
- Recommendations cited "Per NCCN guidelines..." without specific page codes
- No mechanism to retrieve or cite exact NCCN page codes (e.g., "ENDO-4")
- Complete dependence on LLM parametric knowledge — risk of hallucinated content
- Guideline updates required prompt engineering changes, not data updates

**Impact:** In a tumor board setting where treatment decisions affect patient care, ungrounded recommendations lack credibility and auditability.

## Root Cause

The agent was configured in `agents.yaml` with extensive prompt instructions covering disease-specific treatment algorithms, but had no `tools:` binding. Every recommendation was generated from the LLM's training data, which:

1. May not reflect the current NCCN guideline version (v2.2026)
2. Cannot produce exact page codes or footnote references
3. Cannot distinguish between NCCN-preferred vs. other recommended regimens with evidence categories

## Solution

Built a two-stage system: offline PDF preprocessing pipeline + runtime Semantic Kernel plugin.

### Architecture

```
Stage 1 (Offline — run quarterly)
  NCCN PDFs → nccn_pdf_processor.py → Structured JSON
                ├── Algorithm pages → PyMuPDF + GPT-4o vision → decision trees
                ├── Tables → Docling TableFormer → structured markdown
                └── Text/Principles → Docling → clean markdown

Stage 2 (Runtime)
  ClinicalGuidelines Agent → nccn_guidelines.py plugin
                              ├── lookup_nccn_page("ENDO-4")
                              ├── search_nccn_guidelines("endometrial", "Stage IB adjuvant")
                              └── get_nccn_systemic_therapy("endometrial", "recurrent", "dMMR")
```

### Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `scripts/nccn_pdf_processor.py` | Created | Docling + PyMuPDF + GPT-4o vision preprocessing |
| `src/scenarios/default/tools/nccn_guidelines.py` | Created | Runtime Semantic Kernel plugin (3 kernel functions) |
| `src/scenarios/default/config/agents.yaml` | Modified | Tool binding + citation instructions |
| `data/nccn_guidelines/*.json` | Created | Processed guideline data (gitignored) |
| `data/nccn_guidelines/manifest.json` | Created | Version tracking |
| `src/tests/test_local_agents.py` | Modified | 13 new tests (plugin + E2E) |

### Implementation Details

**Two-Library PDF Pipeline:**
- **Docling (IBM)**: 97.9% table structure accuracy via TableFormer; clean markdown for text/principles pages
- **PyMuPDF**: Spatial text coordinates + vector drawing geometry for algorithm pages; renders PNG at 144 DPI
- **GPT-4o Vision**: Reconstructs algorithm flowcharts as structured nodes/edges JSON from rendered page images + spatial coordinate hints

**Plugin Design:**
```python
def create_plugin(plugin_config: PluginConfiguration):
    return NCCNGuidelinesPlugin(plugin_config)

class NCCNGuidelinesPlugin:
    # Class-level cache — loaded once, shared across all conversations
    _loaded: bool = False
    _pages: dict[str, dict] = {}          # page_code -> page data
    _disease_index: dict[str, list] = {}  # disease -> [page_codes]
    _keyword_index: dict[str, set] = {}   # keyword -> {page_codes}
```

**Three Kernel Functions:**

| Function | Parameters | Purpose |
|----------|-----------|---------|
| `lookup_nccn_page` | `page_code: str` | Direct retrieval by NCCN code (e.g., "ENDO-4") |
| `search_nccn_guidelines` | `cancer_type, clinical_question` | Keyword search with weighted scoring (algorithm 3x, table 2.5x, principles 2x) |
| `get_nccn_systemic_therapy` | `cancer_type, setting, biomarkers` | Therapy tables filtered by setting and biomarker status |

**Key Decisions:**
1. **In-memory keyword index** (not vector DB) — sufficient for ~350 pages across 3 guidelines, no infrastructure cost
2. **30K char response cap** — prevents context window pressure when agent processes results
3. **Duplicate page code merging** — NCCN principles pages span multiple PDF pages with same code (e.g., ENDO-A 1/4 through 4/4)
4. **Class-level lazy loading** — single load pass on first plugin use; no per-conversation overhead
5. **Gitignored data** — NCCN content is copyrighted; manifest.json tracks versions without exposing content

**Agent Configuration (agents.yaml):**
```yaml
- name: ClinicalGuidelines
  tools:
    - name: nccn_guidelines
  instructions: |
    Before making any treatment recommendation:
    1. Use search_nccn_guidelines to find relevant algorithm pages
    2. Use lookup_nccn_page for cross-referenced pages
    3. Use get_nccn_systemic_therapy for regimen recommendations
    4. Always cite the specific NCCN page code (e.g., "Per ENDO-4...")
    
    Loaded Guidelines (use tool): Uterine v2.2026, Vaginal v2.2026, Vulvar v2.2026
    Not loaded (training knowledge): Ovarian, Cervical, GTD
```

### Processed Data

| Guideline | Pages | Algorithm Pages | JSON Size |
|-----------|-------|-----------------|-----------|
| Uterine Neoplasms v2.2026 | 150 | 29 | ~915 KB |
| Vaginal Cancer v2.2026 | 65 | 10 | ~352 KB |
| Vulvar Cancer v2.2026 | 86 | 17 | ~435 KB |
| **Total** | **301** | **56** | **~1.7 MB** |

## Verification

**13/13 tests pass:**

- 11 plugin unit tests (TestNCCNGuidelines): load, lookup, search, systemic therapy, edge cases
- 1 config binding test: agents.yaml correctly assigns tool
- 1 E2E test: Agent calls `search_nccn_guidelines` + `get_nccn_systemic_therapy`, produces recommendation citing **ENDO-4**:
  > "Per ENDO-4, for surgically staged Stage IB, Grade 2 endometrioid endometrial carcinoma, the preferred adjuvant therapy is **vaginal brachytherapy**..."

Run tests: `cd src && python3 -m pytest tests/test_local_agents.py::TestNCCNGuidelines tests/test_local_agents.py::TestClinicalGuidelinesE2E -v -p no:logfire`

## Prevention & Maintenance

### Quarterly Update Workflow

NCCN publishes quarterly updates. To update:

```bash
# 1. Download new PDF from NCCN member portal
# 2. Run preprocessing (~5-10 min per PDF, ~$15-25 API cost per guideline)
python3 scripts/nccn_pdf_processor.py --pdf <path_to_pdf>
# 3. Update manifest.json (automatic)
# 4. Run tests to verify
python3 -m pytest tests/test_local_agents.py::TestNCCNGuidelines -v -p no:logfire
# 5. Restart application
```

### Known Limitations

- **Missing guidelines**: Ovarian, Cervical, GTD not yet loaded (agent uses training knowledge for these)
- **Keyword search only**: No semantic/vector search — may miss clinical synonyms ("recurrent" vs "relapse")
- **Vision extraction accuracy**: Complex algorithm pages with overlapping arrows may have structural errors in decision trees
- **No real-time sync**: Batch pipeline, not continuous; version drift possible between quarterly updates

### Future Improvements (Prioritized)

1. **Process ovarian + cervical guidelines** — completes core GYN coverage
2. **Semantic search layer** — vector embeddings for similarity-based guideline retrieval
3. **Version drift detection** — automated alerts when NCCN releases new versions
4. **Algorithm validation pipeline** — secondary GPT-4o verification of decision tree structure

## Related Documentation

- [GYN Tumor Board Adaptation](gyn-tumor-board-adaptation.md) — parent initiative
- `docs/agent_development.md` — Plugin development patterns
- `CLAUDE.md` — Project overview and agent table
- Memory: `project_nccn_guidelines_integration.md` — Project context

## Testing Checklist (New Guideline Addition)

- [ ] PDF readable by PyMuPDF
- [ ] Page codes extracted for >80% of pages
- [ ] Algorithm pages have non-empty decision trees
- [ ] Footnotes and cross-references populated
- [ ] Disease field set correctly for all pages
- [ ] Manifest.json updated with version info
- [ ] Plugin loads without errors (TestNCCNGuidelines passes)
- [ ] Agent cites page codes in E2E test (TestClinicalGuidelinesE2E passes)
