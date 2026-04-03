# Multi-Source Medical Research Plugin
# Searches PubMed (primary), Europe PMC, and Semantic Scholar.
# Synthesizes using RISEN prompt. Post-validates all citations.
# Returns evidence-graded literature review with verified PMID citations.

import asyncio
import json
import logging
import os
import re

import aiohttp
from azure.core.exceptions import ResourceNotFoundError
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import kernel_function

from data_models.chat_artifact import ChatArtifact, ChatArtifactFilename, ChatArtifactIdentifier
from data_models.chat_context import ChatContext
from data_models.data_access import DataAccess
from data_models.plugin_configuration import PluginConfiguration
from utils.model_utils import model_supports_temperature

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SEMANTIC_SCHOLAR_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"

# ---------------------------------------------------------------------------
# Evidence level keywords (used by _infer_evidence_level)
# ---------------------------------------------------------------------------
_LEVEL_I_KEYWORDS = ["meta-analysis", "systematic review", "cochrane"]
_LEVEL_II_KEYWORDS = ["randomized", "phase iii", "phase 3", "rct", "prospective cohort"]
_LEVEL_III_KEYWORDS = ["retrospective", "chart review", "case-control", "registry", "population-based"]
_LEVEL_IV_KEYWORDS = ["case series", "case report"]

# ---------------------------------------------------------------------------
# RISEN synthesis prompt
# ---------------------------------------------------------------------------
SYNTHESIS_PROMPT = """\
=== ROLE ===
You are a medical research librarian at an **academic medical center gynecologic oncology division**.
You have deep expertise in critically appraising evidence, grading study quality, and synthesizing \
literature for subspecialty oncologists at a GYN tumor board.
You are NOT a physician. You do NOT make treatment recommendations. You summarize what the literature says.

=== INSTRUCTIONS ===
You have been provided with a numbered list of retrieved papers. Each paper is tagged with a unique \
identifier (e.g., [Paper-01 | PMID: 12345678]) and includes title, authors, journal, evidence level, \
and abstract.

Synthesize ONLY the information contained in these provided papers into a structured evidence summary. \
Cite every factual claim using the exact PMID from the paper tag: [PMID: 12345678]. \
For papers without a PMID, use [DOI: 10.xxxx/xxxxx].

=== STEPS ===
Follow these steps exactly, in order:

**Step 1 — Inventory.** Read every provided paper. Note its identifier, study type, sample size \
(if stated), and primary finding. Skip any paper whose abstract says "No abstract available."

**Step 2 — Relevance filter.** A paper is relevant ONLY if its abstract explicitly discusses the \
disease site, treatment, biomarker, or clinical question asked. Papers about a different cancer type \
or drug class are NOT relevant — do not cite them.

**Step 3 — Evidence grading.** For each relevant paper, confirm or refine its pre-assigned evidence level:
  - Level I: Systematic review / meta-analysis of RCTs, or large RCT (n > 200)
  - Level II: Smaller RCT (n ≤ 200), or well-designed prospective cohort
  - Level III: Retrospective cohort, case-control, registry study
  - Level IV: Case series, case report
  - Level V: Expert opinion, narrative review, preclinical / in-vitro
Prefer citing Level I–III evidence. Flag any claim supported only by Level IV–V.

**Step 4 — Synthesis.** Write a structured summary organized by clinical relevance \
(most practice-changing evidence first). Use inline citations [PMID: 12345678]. \
Use clinical shorthand: PFS, OS, ORR, HR, CI, FIGO, HGSC, PARP, dMMR, HRD, etc.

**Step 5 — Conflicts and gaps.** Explicitly state if:
  - Evidence is conflicting between studies
  - Fewer than 3 relevant papers were found
  - The available evidence does not directly address the clinical query
  - All cited evidence is Level III or below

=== END GOAL ===
Output this exact structure:

**Evidence Summary: [restate clinical query in one line]**

**Key Findings**
- [2–4 bullet points, each with inline PMID citation]

**Detailed Synthesis**
[Organized by clinical relevance. Every factual claim has an inline citation.]

**Evidence Quality**
[How many papers cited, evidence levels represented, limitations]

**References**
[Numbered list, Vancouver format. Each entry: Authors. Title. Journal. Year;Vol:Pages. \
https://pubmed.ncbi.nlm.nih.gov/PMID/]

=== NARROWING (HARD CONSTRAINTS) ===
1. NEVER fabricate a PMID, DOI, author name, journal name, or study result.
2. NEVER cite a paper that was not provided to you in this prompt. The provided papers are your ONLY source.
3. NEVER extrapolate results beyond what the abstract states. If a study reports PFS but not OS, \
do not claim it showed an OS benefit.
4. NEVER write "studies show" or "evidence suggests" without a specific [PMID: X] citation.
5. If the provided papers do not adequately address the query, state: \
"The retrieved literature does not provide sufficient evidence to address this query."
6. Cite at most 12 papers. Prefer 5–8 high-quality papers over many low-quality ones.
7. Every [PMID: X] or [DOI: X] in your output MUST match exactly one paper tag provided above.
8. Do NOT use your training data to supplement the provided papers. Even if you know about a \
landmark trial, if it is not in the provided papers, do NOT mention it.
9. Do NOT provide treatment recommendations. You summarize evidence; the tumor board decides."""


def create_plugin(plugin_config: PluginConfiguration) -> "MedicalResearchPlugin":
    return MedicalResearchPlugin(
        chat_ctx=plugin_config.chat_ctx,
        data_access=plugin_config.data_access,
        app_ctx=plugin_config.app_ctx,
        kernel=plugin_config.kernel,
    )


class MedicalResearchPlugin:
    def __init__(self, chat_ctx: ChatContext, data_access: DataAccess, app_ctx=None, kernel=None):
        self.chat_ctx = chat_ctx
        self.data_access = data_access
        self.kernel = kernel

    # =====================================================================
    # Main entry point
    # =====================================================================

    @kernel_function(
        description=(
            "Search PubMed, Europe PMC, and Semantic Scholar for GYN oncology literature relevant to a clinical "
            "research query, then synthesize a cited evidence summary using the RISEN framework. "
            "Returns text, sources, and search metadata."
        )
    )
    async def process_prompt(self, prompt: str) -> dict:
        """
        Search PubMed, Europe PMC, and Semantic Scholar for GYN oncology literature,
        then synthesize findings with verified citations.

        Args:
            prompt: A clinical research query.

        Returns:
            dict with keys: text, sources, search_metadata.
        """
        logger.info("MedicalResearch query received (len=%d)", len(prompt))

        # 1. Search all three sources concurrently
        async with aiohttp.ClientSession() as session:
            pubmed_results, europepmc_results, semantic_results = await asyncio.gather(
                self._search_pubmed(session, prompt),
                self._search_europepmc(session, prompt),
                self._search_semantic_scholar(session, prompt),
                return_exceptions=True,
            )

        # Handle failures gracefully — log and continue with whatever succeeded
        if isinstance(pubmed_results, BaseException):
            logger.warning("PubMed search failed: %s", pubmed_results)
            pubmed_results = []
        if isinstance(europepmc_results, BaseException):
            logger.warning("EuropePMC search failed: %s", europepmc_results)
            europepmc_results = []
        if isinstance(semantic_results, BaseException):
            logger.warning("Semantic Scholar search failed: %s", semantic_results)
            semantic_results = []
        source_counts = {
            "pubmed": len(pubmed_results),
            "europepmc": len(europepmc_results),
            "semantic_scholar": len(semantic_results),
        }

        logger.info(
            "Search results — PubMed: %d, EuropePMC: %d, SemanticScholar: %d",
            source_counts.get("pubmed", 0),
            source_counts.get("europepmc", 0),
            source_counts.get("semantic_scholar", 0),
        )

        # 2. PubMed-first dedup + merge
        merged = self._deduplicate_pubmed_first(pubmed_results, europepmc_results, semantic_results)

        # 3. Filter out papers with no abstract
        merged = [p for p in merged if p.get("abstract", "").strip()]
        logger.info("Papers with abstracts after dedup: %d", len(merged))

        # 4. Handle no results
        if not merged:
            return {
                "text": (
                    "**No relevant literature found.**\n\n"
                    "The search across PubMed, Europe PMC, and Semantic Scholar returned no papers "
                    "with abstracts matching this query. Consider:\n"
                    "- Broadening the search terms\n"
                    "- Searching for the drug class instead of a specific agent\n"
                    "- Checking if this is an emerging area with limited published evidence"
                ),
                "sources": {},
                "search_metadata": {**source_counts, "query": prompt, "unique_after_dedup": 0},
            }

        # 5. Infer evidence levels
        for paper in merged:
            paper["evidence_level"] = self._infer_evidence_level(paper.get("abstract", ""))

        # 6. Sort: evidence level asc → citation count desc → year desc. Cap at 12.
        level_order = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
        merged.sort(key=lambda p: (
            level_order.get(p.get("evidence_level", "V"), 5),
            -p.get("citation_count", 0),
            -int(p.get("year", "0") or "0"),
        ))
        papers_for_synthesis = merged[:12]

        # 7. Synthesize with RISEN prompt
        synthesis_text = await self._synthesize(prompt, papers_for_synthesis)

        # 8. Validate citations — remove any PMID/DOI not in source papers
        valid_ids = self._build_valid_id_set(papers_for_synthesis)
        validated_text, removed_count, warnings = self._validate_citations(synthesis_text, valid_ids)
        for w in warnings:
            logger.warning(w)

        if removed_count > 0:
            validated_text += f"\n\n---\n*{removed_count} citation(s) removed during validation — not in retrieved papers.*"

        # 9. Build sources dict (only papers actually cited in validated output)
        sources = self._build_sources_dict(papers_for_synthesis, validated_text)

        # 10. Save for Word doc / PPTX
        await self._save_research_papers(sources)

        return {
            "text": validated_text,
            "sources": sources,
            "search_metadata": {
                **source_counts,
                "query": prompt,
                "unique_after_dedup": len(merged),
                "sent_to_synthesis": len(papers_for_synthesis),
                "citations_removed": removed_count,
            },
        }

    # =====================================================================
    # PubMed E-utilities (primary source)
    # =====================================================================

    async def _search_pubmed(self, session: aiohttp.ClientSession, query: str) -> list[dict]:
        """Search PubMed and return metadata + abstracts."""
        params = {
            "db": "pubmed",
            "term": f"{query} AND (gynecologic oncology OR ovarian cancer OR endometrial cancer OR cervical cancer)",
            "retmax": 15,
            "sort": "relevance",
            "retmode": "json",
        }
        api_key = os.environ.get("NCBI_API_KEY")
        if api_key:
            params["api_key"] = api_key

        async with session.get(PUBMED_ESEARCH, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        # EFetch abstracts (XML) + ESummary metadata (JSON) concurrently
        fetch_params = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
        summary_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
        if api_key:
            fetch_params["api_key"] = api_key
            summary_params["api_key"] = api_key

        async def _fetch_efetch() -> str:
            async with session.get(PUBMED_EFETCH, params=fetch_params) as resp:
                resp.raise_for_status()
                return await resp.text()

        async def _fetch_esummary() -> dict:
            async with session.get(PUBMED_ESUMMARY, params=summary_params) as resp:
                resp.raise_for_status()
                return await resp.json()

        xml_text, summary_data = await asyncio.gather(_fetch_efetch(), _fetch_esummary())

        results = []
        for pmid in pmids:
            doc = summary_data.get("result", {}).get(pmid, {})
            if not doc or pmid == "uids":
                continue
            authors_list = doc.get("authors", [])
            author_str = ", ".join(a.get("name", "") for a in authors_list[:5])
            if len(authors_list) > 5:
                author_str += " et al."
            results.append({
                "pmid": pmid,
                "title": doc.get("title", ""),
                "authors": author_str,
                "journal": doc.get("fulljournalname", doc.get("source", "")),
                "year": doc.get("pubdate", "")[:4],
                "doi": doc.get("elocationid", "").replace("doi: ", ""),
                "abstract": self._extract_abstract_from_xml(xml_text, pmid),
                "source_db": "pubmed",
                "priority": 1,
            })
        return results

    @staticmethod
    def _extract_abstract_from_xml(xml_text: str, pmid: str) -> str:
        pattern = rf'<PMID[^>]*>{pmid}</PMID>.*?</PubmedArticle>'
        match = re.search(pattern, xml_text, re.DOTALL)
        if not match:
            return ""
        article_xml = match.group(0)
        abstract_parts = re.findall(r'<AbstractText[^>]*>(.*?)</AbstractText>', article_xml, re.DOTALL)
        if abstract_parts:
            return " ".join(re.sub(r'<[^>]+>', '', part) for part in abstract_parts).strip()
        return ""

    # =====================================================================
    # Europe PMC (supplementary — full-text enrichment)
    # =====================================================================

    async def _search_europepmc(self, session: aiohttp.ClientSession, query: str) -> list[dict]:
        params = {"query": query, "format": "json", "pageSize": 10, "resultType": "core"}
        async with session.get(EUROPEPMC_SEARCH, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
        results = []
        for item in data.get("resultList", {}).get("result", []):
            results.append({
                "pmid": item.get("pmid") or None,
                "title": item.get("title", ""),
                "authors": item.get("authorString", ""),
                "journal": item.get("journalTitle", ""),
                "year": str(item.get("pubYear", "")),
                "doi": item.get("doi", ""),
                "abstract": item.get("abstractText", ""),
                "source_db": "europepmc",
                "priority": 2,
            })
        return results

    # =====================================================================
    # Semantic Scholar (supplementary — citation counts)
    # =====================================================================

    async def _search_semantic_scholar(self, session: aiohttp.ClientSession, query: str) -> list[dict]:
        params = {
            "query": query,
            "limit": 10,
            "fields": "paperId,externalIds,title,abstract,authors,journal,year,citationCount,influentialCitationCount",
        }
        headers = {}
        s2_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if s2_key:
            headers["x-api-key"] = s2_key
        async with session.get(SEMANTIC_SCHOLAR_SEARCH, params=params, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
        results = []
        for paper in data.get("data", []):
            ext_ids = paper.get("externalIds", {}) or {}
            authors_list = paper.get("authors", []) or []
            author_str = ", ".join(a.get("name", "") for a in authors_list[:5])
            if len(authors_list) > 5:
                author_str += " et al."
            results.append({
                "pmid": ext_ids.get("PubMed"),
                "title": paper.get("title", ""),
                "authors": author_str,
                "journal": (paper.get("journal") or {}).get("name", ""),
                "year": str(paper.get("year", "")),
                "doi": ext_ids.get("DOI", ""),
                "abstract": paper.get("abstract", "") or "",
                "citation_count": paper.get("citationCount", 0),
                "influential_citations": paper.get("influentialCitationCount", 0),
                "source_db": "semantic_scholar",
                "priority": 3,
            })
        return results

    # =====================================================================
    # PubMed-first deduplication + merge
    # =====================================================================

    def _deduplicate_pubmed_first(
        self,
        pubmed: list[dict],
        europepmc: list[dict],
        semantic: list[dict],
    ) -> list[dict]:
        """Merge with PubMed as canonical source. Enrich with Europe PMC + Semantic Scholar."""
        canonical: dict[str, dict] = {}  # keyed by PMID
        doi_index: dict[str, str] = {}   # DOI → PMID
        title_index: dict[str, str] = {} # normalized title → PMID

        def _norm_title(t: str) -> str:
            return t.lower().strip()[:80] if t else ""

        # Phase 1: PubMed papers are canonical
        for paper in pubmed:
            pmid = paper.get("pmid")
            if not pmid or pmid in canonical:
                continue
            canonical[pmid] = paper
            doi = (paper.get("doi") or "").lower().strip()
            if doi:
                doi_index[doi] = pmid
            title = _norm_title(paper.get("title", ""))
            if title:
                title_index[title] = pmid

        # Phase 2: Europe PMC — enrich existing or add new
        for paper in europepmc:
            pmid = paper.get("pmid")
            doi = (paper.get("doi") or "").lower().strip()
            title = _norm_title(paper.get("title", ""))

            existing_pmid = (
                (pmid if pmid and pmid in canonical else None)
                or doi_index.get(doi)
                or title_index.get(title)
            )

            if existing_pmid:
                # Enrich: fill in abstract if PubMed had none
                if not canonical[existing_pmid].get("abstract") and paper.get("abstract"):
                    canonical[existing_pmid]["abstract"] = paper["abstract"]
                canonical[existing_pmid]["full_text_url"] = f"https://europepmc.org/article/med/{existing_pmid}"
            else:
                # New paper from Europe PMC
                key = pmid or doi or title
                if not key or key in canonical:
                    continue
                canonical[key] = paper
                if doi:
                    doi_index[doi] = key
                if title:
                    title_index[title] = key

        # Phase 3: Semantic Scholar — enrich with citation counts or add new
        for paper in semantic:
            pmid = paper.get("pmid")
            doi = (paper.get("doi") or "").lower().strip()
            title = _norm_title(paper.get("title", ""))

            existing_key = (
                (pmid if pmid and pmid in canonical else None)
                or doi_index.get(doi)
                or title_index.get(title)
            )

            if existing_key:
                # Enrich with citation counts
                canonical[existing_key]["citation_count"] = paper.get("citation_count", 0)
                canonical[existing_key]["influential_citations"] = paper.get("influential_citations", 0)
            else:
                key = pmid or doi or title
                if not key or key in canonical:
                    continue
                canonical[key] = paper
                if doi:
                    doi_index[doi] = key
                if title:
                    title_index[title] = key

        return list(canonical.values())

    # =====================================================================
    # Evidence level inference
    # =====================================================================

    @staticmethod
    def _infer_evidence_level(abstract: str) -> str:
        """Heuristic evidence level from abstract keywords. Refined during synthesis."""
        text = abstract.lower()
        for kw in _LEVEL_I_KEYWORDS:
            if kw in text:
                return "I"
        for kw in _LEVEL_II_KEYWORDS:
            if kw in text:
                return "II"
        for kw in _LEVEL_III_KEYWORDS:
            if kw in text:
                return "III"
        for kw in _LEVEL_IV_KEYWORDS:
            if kw in text:
                return "IV"
        return "V"

    # =====================================================================
    # LLM synthesis (RISEN prompt)
    # =====================================================================

    async def _synthesize(self, query: str, papers: list[dict]) -> str:
        """Build tagged paper context and run RISEN synthesis."""
        papers_context = []
        for i, paper in enumerate(papers, 1):
            pmid_str = f"PMID: {paper['pmid']}" if paper.get("pmid") else ""
            doi_str = f"DOI: {paper['doi']}" if paper.get("doi") else ""
            id_str = pmid_str or doi_str or f"NO-ID-{i}"

            abstract = paper.get("abstract", "").strip()
            if len(abstract) > 2000:
                abstract = abstract[:2000] + " [truncated]"

            level = paper.get("evidence_level", "V")
            cites = paper.get("citation_count", "N/A")

            papers_context.append(
                f"=== [Paper-{i:02d} | {id_str}] ===\n"
                f"Title: {paper.get('title', 'Unknown')}\n"
                f"Authors: {paper.get('authors', 'Unknown')}\n"
                f"Journal: {paper.get('journal', 'Unknown')} ({paper.get('year', 'Unknown')})\n"
                f"Evidence Level (pre-assigned): {level}\n"
                f"Citation Count: {cites}\n"
                f"Source: {paper.get('source_db', 'unknown')}\n"
                f"Abstract:\n{abstract}\n"
                f"=== END Paper-{i:02d} ==="
            )

        context = "\n\n".join(papers_context)

        # Augment prompt for limited evidence
        limited_warning = ""
        if len(papers) < 3:
            limited_warning = (
                f"\n\nNOTE: Only {len(papers)} paper(s) retrieved. This is very limited evidence. "
                "Be especially conservative in your conclusions and explicitly flag the limited evidence base."
            )

        chat_history = ChatHistory()
        chat_history.add_system_message(SYNTHESIS_PROMPT)
        chat_history.add_user_message(
            f"**Clinical Query:** {query}{limited_warning}\n\n"
            f"**Retrieved Literature ({len(papers)} papers):**\n\n{context}"
        )

        if model_supports_temperature():
            settings = AzureChatPromptExecutionSettings(temperature=0.0)
        else:
            settings = AzureChatPromptExecutionSettings()

        chat_service = self.kernel.get_service(service_id="default")
        response = await chat_service.get_chat_message_content(
            chat_history=chat_history, settings=settings
        )
        return str(response)

    # =====================================================================
    # Post-synthesis citation validation
    # =====================================================================

    @staticmethod
    def _build_valid_id_set(papers: list[dict]) -> set[str]:
        """Build set of all valid PMIDs and DOIs from source papers."""
        valid = set()
        for paper in papers:
            pmid = paper.get("pmid")
            if pmid:
                valid.add(pmid.strip())
            doi = paper.get("doi", "").strip()
            if doi:
                valid.add(doi.lower())
        return valid

    @staticmethod
    def _validate_citations(text: str, valid_ids: set[str]) -> tuple[str, int, list[str]]:
        """
        Validate every [PMID: X] and [DOI: X] in synthesis output.
        Remove invalid citations. Return cleaned text, count removed, warnings.
        """
        warnings = []
        removed = 0

        def _check_pmid(match: re.Match) -> str:
            nonlocal removed
            pmid = match.group(1).strip()
            if pmid in valid_ids:
                return match.group(0)
            removed += 1
            warnings.append(f"Hallucinated citation removed: [PMID: {pmid}] — not in retrieved papers")
            return "[citation removed]"

        def _check_doi(match: re.Match) -> str:
            nonlocal removed
            doi = match.group(1).strip().lower()
            if doi in valid_ids:
                return match.group(0)
            removed += 1
            warnings.append(f"Hallucinated citation removed: [DOI: {doi}] — not in retrieved papers")
            return "[citation removed]"

        text = re.sub(r'\[PMID:\s*(\d+)\]', _check_pmid, text)
        text = re.sub(r'\[DOI:\s*([^\]]+)\]', _check_doi, text)

        return text, removed, warnings

    # =====================================================================
    # Build sources dict (only for papers actually cited)
    # =====================================================================

    @staticmethod
    def _build_sources_dict(papers: list[dict], validated_text: str) -> dict:
        """Build sources dict containing only papers that are actually cited in the output."""
        # Extract all cited PMIDs from validated text
        cited_pmids = set(re.findall(r'\[PMID:\s*(\d+)\]', validated_text))
        cited_dois = set(m.lower() for m in re.findall(r'\[DOI:\s*([^\]]+)\]', validated_text))

        sources = {}
        for paper in papers:
            pmid = paper.get("pmid")
            doi = (paper.get("doi") or "").lower().strip()

            if pmid and pmid in cited_pmids:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                sources[pmid] = {
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", ""),
                    "link": f"[{paper.get('title', 'Link')}]({url})",
                    "url": url,
                    "journal": paper.get("journal", ""),
                    "year": paper.get("year", ""),
                    "evidence_level": paper.get("evidence_level", ""),
                }
            elif doi and doi in cited_dois:
                url = f"https://doi.org/{paper.get('doi', '')}"
                sources[doi] = {
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", ""),
                    "link": f"[{paper.get('title', 'Link')}]({url})",
                    "url": url,
                    "journal": paper.get("journal", ""),
                    "year": paper.get("year", ""),
                    "evidence_level": paper.get("evidence_level", ""),
                }
        return sources

    # =====================================================================
    # Artifact persistence (same interface as GraphRAG)
    # =====================================================================

    async def _save_research_papers(self, papers: dict) -> None:
        """Save research papers to chat artifacts for Word doc generation."""
        artifact_id = ChatArtifactIdentifier(
            conversation_id=self.chat_ctx.conversation_id,
            patient_id=self.chat_ctx.patient_id,
            filename=ChatArtifactFilename.RESEARCH_PAPERS,
        )
        try:
            artifact = await self.data_access.chat_artifact_accessor.read(artifact_id)
            research_papers = json.loads(artifact.data.decode("utf-8"))
            research_papers.update(papers)
        except ResourceNotFoundError:
            research_papers = papers
        except json.JSONDecodeError as exc:
            logger.warning("_save_research_papers: corrupt blob content, resetting: %s", exc)
            research_papers = papers
        except Exception:
            logger.exception("_save_research_papers: unexpected error reading blob; re-raising")
            raise

        try:
            await self.data_access.chat_artifact_accessor.write(
                ChatArtifact(artifact_id=artifact_id, data=json.dumps(research_papers).encode("utf-8"))
            )
        except Exception:
            logger.warning(
                "_save_research_papers: failed to persist research papers to blob", exc_info=True
            )
