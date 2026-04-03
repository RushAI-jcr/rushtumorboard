# NCCN Clinical Practice Guidelines Lookup Tool
#
# Provides grounded, citable guideline content to the ClinicalGuidelines agent.
# Loads pre-processed JSON files (from scripts/nccn_pdf_processor.py) at startup
# and exposes three kernel functions: page lookup, clinical scenario search,
# and systemic therapy regimen query.
#
# No external runtime dependencies beyond the standard library.

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import ClassVar

from semantic_kernel.functions import kernel_function

from data_models.plugin_configuration import PluginConfiguration

logger = logging.getLogger(__name__)

MAX_RESPONSE_CHARS = 30_000  # Cap responses to manage context window


def create_plugin(plugin_config: PluginConfiguration) -> "NCCNGuidelinesPlugin":
    return NCCNGuidelinesPlugin(plugin_config)


class NCCNGuidelinesPlugin:
    """Semantic Kernel plugin for NCCN guideline retrieval.

    Lazy-loads pre-processed guideline JSON from data/nccn_guidelines/ on first use.
    Builds in-memory indices for fast lookup by page code, disease site, and keywords.
    """

    # Class-level cache — shared across all conversations, loaded once
    _loaded: ClassVar[bool] = False
    _pages: ClassVar[dict[str, dict]] = {}          # page_code → page data
    _disease_index: ClassVar[dict[str, list]] = {}  # disease → [page_codes]
    _type_index: ClassVar[dict[str, list]] = {}     # content_type → [page_codes]
    _keyword_index: ClassVar[dict[str, set]] = {}   # keyword → {page_codes}
    _guidelines: ClassVar[list[dict]] = []           # metadata per guideline
    _load_lock: ClassVar[threading.Lock] = threading.Lock()

    _CANCER_TYPE_MAP: ClassVar[dict[str, str]] = {
        "endometrial": "endometrial_carcinoma",
        "uterine": "endometrial_carcinoma",
        "uterine carcinoma": "endometrial_carcinoma",
        "endometrial carcinoma": "endometrial_carcinoma",
        "uterine sarcoma": "uterine_sarcoma",
        "sarcoma": "uterine_sarcoma",
        "leiomyosarcoma": "uterine_sarcoma",
        "vaginal": "vaginal_cancer",
        "vaginal cancer": "vaginal_cancer",
        "vagina": "vaginal_cancer",
        "vulvar": "vulvar_cancer",
        "vulvar cancer": "vulvar_cancer",
        "melanoma": "vulvovaginal_melanoma",
        "vulvovaginal melanoma": "vulvovaginal_melanoma",
        "ovarian": "ovarian_cancer",
        "ovarian cancer": "ovarian_cancer",
        "epithelial ovarian": "ovarian_cancer",
        "fallopian tube": "ovarian_cancer",
        "peritoneal": "ovarian_cancer",
        "primary peritoneal": "ovarian_cancer",
        "lcoc": "less_common_ovarian_cancers",
        "germ cell": "less_common_ovarian_cancers",
        "sex cord stromal": "less_common_ovarian_cancers",
        "borderline ovarian": "less_common_ovarian_cancers",
        "low-grade serous": "less_common_ovarian_cancers",
        "mucinous ovarian": "less_common_ovarian_cancers",
        "cervical": "cervical_cancer",
        "cervical cancer": "cervical_cancer",
        "cervix": "cervical_cancer",
        "gtn": "gestational_trophoblastic_neoplasia",
        "gestational trophoblastic": "gestational_trophoblastic_neoplasia",
        "gestational trophoblastic neoplasia": "gestational_trophoblastic_neoplasia",
        "choriocarcinoma": "gestational_trophoblastic_neoplasia",
        "hydatidiform mole": "hydatidiform_mole",
        "molar pregnancy": "hydatidiform_mole",
    }

    def __init__(self, config: PluginConfiguration):
        self._ensure_loaded()

    @classmethod
    def _ensure_loaded(cls):
        """Lazy-load all guideline JSON files into memory (thread-safe, double-checked locking)."""
        if cls._loaded:
            return
        with cls._load_lock:
            if cls._loaded:
                return

            data_dir = cls._find_data_dir()
            if not data_dir:
                logger.warning("NCCN guidelines data directory not found — plugin will return empty results")
                cls._loaded = True
                return

            manifest_path = data_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                # Skip Evidence Blocks files — they duplicate base guideline pages and
                # cause merged page codes to balloon (e.g., OV-D → 116K chars).
                # Base files already contain all algorithm/principles content.
                json_files = [
                    data_dir / g["json_file"]
                    for g in manifest.get("guidelines", [])
                    if "_blocks_" not in g.get("json_file", "")
                ]
            else:
                # Fallback: load all JSON files in directory (skip blocks)
                json_files = sorted(data_dir.glob("*.json"))
                json_files = [f for f in json_files if f.name != "manifest.json" and "_blocks_" not in f.name]

            for json_path in json_files:
                if not json_path.exists():
                    logger.warning("Guideline file not found: %s", json_path)
                    continue
                cls._load_guideline(json_path)

            logger.info(
                "NCCN guidelines loaded: %d guidelines, %d pages, %d unique page codes",
                len(cls._guidelines), sum(len(v) for v in cls._disease_index.values()), len(cls._pages),
            )
            cls._loaded = True

    @classmethod
    def _find_data_dir(cls) -> Path | None:
        """Locate data/nccn_guidelines/ relative to the source tree.

        Checks NCCN_DATA_DIR env var first, then falls back to relative paths.
        """
        env_dir = os.environ.get("NCCN_DATA_DIR")
        if env_dir:
            resolved = Path(env_dir).resolve()
            # Validate the path contains expected guideline structure
            if resolved.is_dir() and (resolved / "manifest.json").exists():
                return resolved
            if resolved.is_dir():
                logger.warning("NCCN_DATA_DIR=%s exists but has no manifest.json — skipping", env_dir)
            else:
                logger.warning("NCCN_DATA_DIR=%s does not exist or is not a directory", env_dir)

        # From src/scenarios/default/tools/ → ../../../../data/nccn_guidelines/
        tools_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            tools_dir / ".." / ".." / ".." / ".." / "data" / "nccn_guidelines",
            tools_dir / ".." / ".." / ".." / "data" / "nccn_guidelines",
            Path(os.getcwd()) / "data" / "nccn_guidelines",
        ]
        for c in candidates:
            resolved = c.resolve()
            if resolved.is_dir():
                return resolved
        return None

    @classmethod
    def _load_guideline(cls, json_path: Path):
        """Load a single guideline JSON file into the class-level indices."""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        guideline_meta = {
            "name": data.get("guideline_name", "Unknown"),
            "version": data.get("version", ""),
            "version_date": data.get("version_date", ""),
            "source": json_path.name,
        }
        cls._guidelines.append(guideline_meta)

        for page in data.get("pages", []):
            code = page.get("page_code")
            if not code:
                continue

            # Handle duplicate codes (e.g., ENDO-A appears on multiple pages)
            # Merge content by appending markdown
            if code in cls._pages:
                existing = cls._pages[code]
                existing["markdown"] += "\n\n---\n\n" + page.get("markdown", "")
                # Merge footnotes
                for k, v in page.get("footnotes", {}).items():
                    existing.setdefault("footnotes", {})[k] = v
                # Merge cross-references
                existing_refs = set(existing.get("cross_references", []))
                existing_refs.update(page.get("cross_references", []))
                existing["cross_references"] = sorted(existing_refs)
                # Merge tables
                if "tables" in page:
                    existing.setdefault("tables", []).extend(page["tables"])
                continue

            page_entry = {
                "page_code": code,
                "page_num": page.get("page_num"),
                "content_type": page.get("content_type", "text"),
                "disease": page.get("disease", ""),
                "title": page.get("title", ""),
                "markdown": page.get("markdown", ""),
                "decision_tree": page.get("decision_tree"),
                "footnotes": page.get("footnotes", {}),
                "cross_references": page.get("cross_references", []),
                "guideline": guideline_meta["name"],
                "version": guideline_meta["version"],
            }
            if "tables" in page:
                page_entry["tables"] = page["tables"]

            cls._pages[code] = page_entry

            # Disease index
            disease = page.get("disease", "unknown")
            cls._disease_index.setdefault(disease, []).append(code)

            # Content type index
            ctype = page.get("content_type", "text")
            cls._type_index.setdefault(ctype, []).append(code)

            # Keyword index — extract searchable terms from title, markdown, disease
            keywords = cls._extract_keywords(page)
            for kw in keywords:
                cls._keyword_index.setdefault(kw, set()).add(code)

    @staticmethod
    def _extract_keywords(page: dict) -> set[str]:
        """Extract searchable keywords from a page for the inverted index."""
        keywords = set()
        text = " ".join([
            page.get("title", ""),
            page.get("disease", ""),
            page.get("page_code", ""),
            page.get("markdown", "")[:2000],  # First 2K chars only for efficiency
        ]).lower()

        # Disease terms
        disease_terms = [
            "endometrial", "uterine", "vaginal", "vulvar", "cervical",
            "ovarian", "fallopian tube", "peritoneal", "epithelial ovarian",
            "cervix", "gestational trophoblastic", "hydatidiform mole",
            "choriocarcinoma", "neuroendocrine",
            "sarcoma", "melanoma", "carcinoma", "adenocarcinoma",
            "squamous", "serous", "clear cell", "carcinosarcoma",
            "leiomyosarcoma", "stromal", "pecoma",
            "mucinous", "germ cell", "sex cord", "borderline",
            "low-grade serous", "high-grade serous", "endometrioid",
        ]
        for term in disease_terms:
            if term in text:
                keywords.add(term)

        # Stage terms
        for stage in ["stage i", "stage ii", "stage iii", "stage iv",
                      "stage ia", "stage ib", "stage ic",
                      "stage iia", "stage iib", "stage iiia", "stage iiib", "stage iiic",
                      "stage iva", "stage ivb"]:
            if stage in text:
                keywords.add(stage)

        # Treatment modality terms
        treatment_terms = [
            "surgery", "hysterectomy", "bso", "lymphadenectomy",
            "chemotherapy", "systemic therapy", "radiation", "ebrt",
            "brachytherapy", "immunotherapy", "targeted therapy",
            "hormone therapy", "progestin", "fertility",
            "parp", "pembrolizumab", "dostarlimab", "lenvatinib",
            "bevacizumab", "carboplatin", "paclitaxel", "cisplatin",
            "olaparib", "niraparib", "rucaparib", "mirvetuximab",
            "gemcitabine", "doxorubicin", "topotecan", "etoposide",
            "hipec", "cytoreduction", "debulking", "interval",
            "chemoradiation", "cone biopsy", "trachelectomy",
            "methotrexate", "actinomycin", "ema-co", "hcg",
            "tisotumab", "cemiplimab",
            "sentinel lymph node", "adjuvant", "neoadjuvant",
            "recurrent", "recurrence", "surveillance", "follow-up",
            "maintenance", "palliative",
        ]
        for term in treatment_terms:
            if term in text:
                keywords.add(term)

        # Biomarker terms
        biomarker_terms = [
            "mmr", "dmmr", "pmmr", "msi", "msi-h", "mss",
            "pole", "p53", "nsmp", "her2", "brca", "brca1", "brca2", "hrd",
            "pd-l1", "figo", "lvsi", "er+", "pr+",
            "ca-125", "he4", "platinum-sensitive", "platinum-resistant",
            "hpv", "pd-l1 cps", "who score",
        ]
        for term in biomarker_terms:
            if term in text:
                keywords.add(term)

        # Clinical scenario terms
        scenario_terms = [
            "primary treatment", "adjuvant", "workup", "evaluation",
            "locoregional", "distant metastases", "relapse",
            "fertility-sparing", "incompletely staged",
        ]
        for term in scenario_terms:
            if term in text:
                keywords.add(term)

        return keywords

    def _format_page_response(self, page: dict, include_full_markdown: bool = True) -> str:
        """Format a page entry as a JSON string for the agent."""
        result = {
            "page_code": page["page_code"],
            "guideline": page.get("guideline", ""),
            "version": page.get("version", ""),
            "content_type": page["content_type"],
            "disease": page.get("disease", ""),
            "title": page.get("title", ""),
        }

        if include_full_markdown:
            md = page.get("markdown", "")
            if len(md) > MAX_RESPONSE_CHARS:
                md = md[:MAX_RESPONSE_CHARS] + "\n\n[... truncated ...]"
            result["content"] = md

        if page.get("decision_tree"):
            result["decision_tree"] = page["decision_tree"]

        if page.get("footnotes"):
            result["footnotes"] = page["footnotes"]

        if page.get("cross_references"):
            result["cross_references"] = page["cross_references"]

        if page.get("tables"):
            # Include table markdown but cap size
            table_content = []
            total_len = 0
            for t in page["tables"]:
                tmd = t.get("markdown", "")
                if total_len + len(tmd) > MAX_RESPONSE_CHARS // 2:
                    break
                table_content.append(tmd)
                total_len += len(tmd)
            result["tables"] = table_content

        return json.dumps(result, indent=2, ensure_ascii=False)

    @kernel_function(
        description="Look up a specific NCCN guideline page by its code "
        "(e.g., ENDO-1, VAG-3, VULVA-E, OV-1, OV-D, LCOC-1, CERV-1, CERV-F, GTN-1, HM-1, ST-1). "
        "Returns the full content including decision trees, treatment algorithms, "
        "footnotes, and cross-references to related pages. "
        "Use this when you know the specific page code you need."
    )
    async def lookup_nccn_page(self, page_code: str) -> str:
        """Retrieve a specific NCCN guideline page by its code."""
        code = page_code.strip().upper()

        if code in self._pages:
            page = self._pages[code]
            logger.info("NCCN lookup: %s → %s (%s)", code, page["title"], page["content_type"])
            return self._format_page_response(page)

        # Try partial match (e.g., "ENDO4" → "ENDO-4")
        normalized = re.sub(r"(\D)(\d)", r"\1-\2", code)
        if normalized in self._pages:
            return self._format_page_response(self._pages[normalized])

        # List available codes for the prefix
        prefix = code.split("-")[0] if "-" in code else code[:4]
        available = [c for c in self._pages if c.startswith(prefix)]
        return json.dumps({
            "error": f"Page code '{page_code}' not found",
            "available_codes_for_prefix": sorted(available)[:20],
            "hint": "Try one of the available codes listed above",
        })

    @kernel_function(
        description="Search NCCN guidelines for a specific clinical scenario. "
        "Provide the cancer type (endometrial, vaginal, vulvar, uterine sarcoma, ovarian, cervical, GTN) "
        "and a clinical question describing the patient's situation "
        "(e.g., 'Stage IIIC endometrial carcinoma adjuvant treatment', "
        "'recurrent vulvar cancer therapy options', "
        "'Stage IIIC ovarian cancer primary treatment', "
        "'BRCA+ ovarian cancer maintenance therapy', "
        "'Stage IB2 cervical cancer primary treatment', "
        "'low-risk GTN treatment'). "
        "Returns the most relevant guideline pages with treatment algorithms."
    )
    async def search_nccn_guidelines(self, cancer_type: str, clinical_question: str) -> str:
        """Search NCCN guidelines by cancer type and clinical question."""
        query = f"{cancer_type} {clinical_question}".lower()

        # Extract search keywords from the query
        query_keywords = set()
        # Add all individual words (3+ chars)
        for word in re.findall(r"[a-z][a-z0-9-]+", query):
            if len(word) >= 3:
                query_keywords.add(word)

        # Also match multi-word terms
        all_terms = set()
        for kw_set in self._keyword_index:
            if kw_set in query:
                all_terms.add(kw_set)
        query_keywords.update(all_terms)

        # Down-weight overly broad terms that match most pages
        _BROAD_TERMS = {"carcinoma", "adenocarcinoma", "surgery", "chemotherapy", "radiation", "stage i", "stage ii", "stage iii", "stage iv"}

        # Score pages by keyword overlap
        page_scores: dict[str, float] = {}
        for kw in query_keywords:
            matching_codes = self._keyword_index.get(kw, set())
            for code in matching_codes:
                # Weight algorithm pages higher than discussion
                page = self._pages.get(code)
                if not page:
                    continue
                weight = 1.0
                if page["content_type"] == "algorithm":
                    weight = 3.0
                elif page["content_type"] == "principles":
                    weight = 2.0
                elif page["content_type"] == "table":
                    weight = 2.5
                elif page["content_type"] == "staging":
                    weight = 1.5
                elif page["content_type"] == "discussion":
                    weight = 0.5
                if kw in _BROAD_TERMS:
                    weight *= 0.3
                page_scores[code] = page_scores.get(code, 0) + weight

        if not page_scores:
            # Fallback: return all algorithm pages for the disease
            disease_key = self._map_cancer_type(cancer_type)
            codes = self._disease_index.get(disease_key, [])
            algo_codes = [c for c in codes if self._pages.get(c, {}).get("content_type") == "algorithm"]
            if algo_codes:
                results = []
                for code in algo_codes[:5]:
                    results.append(self._format_page_summary(self._pages[code]))
                return json.dumps({
                    "query": f"{cancer_type}: {clinical_question}",
                    "results_count": len(results),
                    "results": results,
                    "note": "Broad match — showing algorithm pages for this disease site",
                }, indent=2)

            return json.dumps({
                "query": f"{cancer_type}: {clinical_question}",
                "error": "No matching guidelines found",
                "available_diseases": sorted(self._disease_index.keys()),
            })

        # Sort by score descending, take top results
        ranked = sorted(page_scores.items(), key=lambda x: -x[1])

        results = []
        total_chars = 0
        for code, score in ranked[:7]:
            page = self._pages[code]
            page_response = self._format_page_response(page, include_full_markdown=True)
            if total_chars + len(page_response) > MAX_RESPONSE_CHARS:
                # Add summary only for remaining pages
                results.append(self._format_page_summary(page))
            else:
                results.append(json.loads(page_response))
                total_chars += len(page_response)

        return json.dumps({
            "query": f"{cancer_type}: {clinical_question}",
            "results_count": len(results),
            "results": results,
        }, indent=2, ensure_ascii=False)

    @kernel_function(
        description="Get NCCN systemic therapy regimen options for a specific cancer type and setting. "
        "Returns preferred, other recommended, and biomarker-directed therapy options "
        "with NCCN evidence categories. "
        "cancer_type: endometrial, vaginal, vulvar, uterine_sarcoma, ovarian, cervical, or gtn. "
        "setting: primary, adjuvant, recurrent, or maintenance. "
        "biomarkers: optional comma-separated biomarker status (e.g., 'dMMR,MSI-H' or 'HER2+' or 'BRCA+' or 'HRD+')."
    )
    async def get_nccn_systemic_therapy(
        self, cancer_type: str, setting: str, biomarkers: str = ""
    ) -> str:
        """Query systemic therapy tables filtered by clinical setting and biomarkers."""
        # Find systemic therapy pages (typically *-D or *-E suffix)
        therapy_codes = []
        disease_key = self._map_cancer_type(cancer_type)
        _SYSTEMIC_PREFIXES = ("ENDO-D", "VAG-D", "VULVA-E", "UTSARC-C", "OV-D", "LCOC-A", "LCOC-5A", "LCOC-5B", "CERV-F", "GTN-D")

        for code in self._disease_index.get(disease_key, []):
            page = self._pages.get(code)
            if not page:
                continue
            # Systemic therapy pages have specific suffixes
            if any(code.startswith(pfx) for pfx in _SYSTEMIC_PREFIXES):
                therapy_codes.append(code)
            # Also match by title keywords
            title = page.get("title", "").lower()
            if "systemic therapy" in title or "chemotherapy" in title:
                if code not in therapy_codes:
                    therapy_codes.append(code)

        if not therapy_codes:
            return json.dumps({
                "cancer_type": cancer_type,
                "setting": setting,
                "error": f"No systemic therapy pages found for {cancer_type}",
                "available_diseases": sorted(self._disease_index.keys()),
            })

        # Collect all therapy content
        results = []
        for code in therapy_codes:
            page = self._pages[code]
            content = {
                "page_code": code,
                "title": page.get("title", ""),
                "version": page.get("version", ""),
            }

            md = page.get("markdown", "")

            # Filter by setting if possible
            setting_lower = setting.lower()
            if setting_lower and setting_lower != "all":
                # Try to find relevant section in markdown
                sections = self._extract_relevant_sections(md, setting_lower)
                if sections:
                    content["content"] = sections
                else:
                    content["content"] = md
            else:
                content["content"] = md

            # Filter by biomarkers if specified
            if biomarkers:
                bm_list = [b.strip().lower() for b in biomarkers.split(",")]
                content["biomarker_filter"] = bm_list
                # Highlight relevant biomarker mentions
                relevant_lines = []
                for line in md.split("\n"):
                    line_lower = line.lower()
                    if any(bm in line_lower for bm in bm_list):
                        relevant_lines.append(line)
                if relevant_lines:
                    content["biomarker_relevant_lines"] = "\n".join(relevant_lines)

            if page.get("tables"):
                content["tables"] = [t.get("markdown", "") for t in page["tables"]]

            if page.get("footnotes"):
                content["footnotes"] = page["footnotes"]

            results.append(content)

        # Build response incrementally, switching to summaries when budget exceeded
        capped_results = []
        total_chars = 0
        for content in results:
            page_json = json.dumps(content, ensure_ascii=False)
            if total_chars + len(page_json) > MAX_RESPONSE_CHARS:
                capped_results.append({
                    "page_code": content.get("page_code", ""),
                    "title": content.get("title", ""),
                    "note": "Content omitted due to size — use lookup_nccn_page for full content",
                })
            else:
                capped_results.append(content)
                total_chars += len(page_json)

        return json.dumps({
            "cancer_type": cancer_type,
            "setting": setting,
            "biomarkers": biomarkers,
            "therapy_pages": capped_results,
        }, indent=2, ensure_ascii=False)

    @classmethod
    def _map_cancer_type(cls, cancer_type: str) -> str:
        """Map user-friendly cancer type to disease index key."""
        ct = cancer_type.lower().strip()
        return cls._CANCER_TYPE_MAP.get(ct, ct)

    @staticmethod
    def _format_page_summary(page: dict) -> dict:
        """Create a compact summary of a page (no full markdown)."""
        return {
            "page_code": page["page_code"],
            "content_type": page["content_type"],
            "disease": page.get("disease", ""),
            "title": page.get("title", ""),
            "cross_references": page.get("cross_references", []),
            "note": "Use lookup_nccn_page to get full content",
        }

    @staticmethod
    def _extract_relevant_sections(markdown: str, setting: str) -> str:
        """Extract sections of markdown relevant to a clinical setting."""
        setting_keywords = {
            "primary": ["primary", "first-line", "front-line", "initial"],
            "adjuvant": ["adjuvant", "post-operative", "postoperative"],
            "recurrent": ["recurrent", "relapse", "second-line", "subsequent", "salvage"],
            "maintenance": ["maintenance", "consolidation"],
            "neoadjuvant": ["neoadjuvant", "preoperative"],
        }

        keywords = setting_keywords.get(setting, [setting])
        relevant_lines = []
        in_section = False

        for line in markdown.split("\n"):
            line_lower = line.lower()
            # Check if this line starts a relevant section
            if any(kw in line_lower for kw in keywords):
                in_section = True
            # Headers reset section tracking
            if line.startswith("#") and not any(kw in line_lower for kw in keywords):
                in_section = False
            if in_section:
                relevant_lines.append(line)

        return "\n".join(relevant_lines) if relevant_lines else ""
