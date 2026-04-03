#!/usr/bin/env python3
"""
NCCN Guideline PDF Processor.

Converts NCCN clinical practice guideline PDFs into structured JSON
for the ClinicalGuidelines agent's nccn_guidelines tool.

Two-library pipeline:
  - PyMuPDF: Extracts spatial text coordinates + vector drawings from
    algorithm/flowchart pages, renders page images for GPT-4o vision.
  - Docling: Extracts tables, principles text, and discussion sections
    with high-fidelity markdown and table structure.

Usage:
    python scripts/nccn_pdf_processor.py --pdf ../uterine.pdf
    python scripts/nccn_pdf_processor.py --pdf ../uterine.pdf --output data/nccn_guidelines/uterine_v2.2026.json
    python scripts/nccn_pdf_processor.py --pdf ../vaginal.pdf --pdf ../vulvar.pdf
"""

import argparse
import base64
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "nccn_guidelines"

# ---------------------------------------------------------------------------
# Page code patterns (bottom-right of every NCCN page)
# ---------------------------------------------------------------------------
# Canonical list of NCCN page code prefixes — add new guidelines here only.
_DISEASE_PREFIXES = ("ENDO", "VAG", "VULVA", "UTSARC", "VM", "UN", "OV", "LCOC", "CERV", "GTN", "HM")
_ALL_PREFIXES = _DISEASE_PREFIXES + ("EB",)  # EB = Evidence Blocks (numeric codes only)
_DISEASE_GROUP = "|".join(_DISEASE_PREFIXES)
_ALL_GROUP = "|".join(_ALL_PREFIXES)

# Algorithm pages: OV-1, CERV-3, EB-3, etc. (numeric suffix)
_ALGO_CODE_RE = re.compile(rf"({_ALL_GROUP})-(\d+[A-Z]?)\s*$", re.MULTILINE)
# Principles pages: OV-A, CERV-D 2 of 4, etc. (letter suffix; EB excluded — uses EB-DEF only)
_PRINCIPLES_CODE_RE = re.compile(rf"({_DISEASE_GROUP})-([A-Z])\s*(\d+\s*of\s*\d+)?\s*$", re.MULTILINE)
# Staging: ST-1, ST-2, ST-3
_STAGING_CODE_RE = re.compile(r"ST-(\d+)\s*$", re.MULTILINE)
# Discussion: MS-1, etc.
_DISCUSSION_CODE_RE = re.compile(r"MS-(\d+)\s*$", re.MULTILINE)
# Abbreviations: ABBR-1
_ABBR_CODE_RE = re.compile(r"ABBR-(\d+)\s*$", re.MULTILINE)
# Evidence Blocks definition: EB-DEF
_EB_DEF_CODE_RE = re.compile(r"EB-DEF\s*$", re.MULTILINE)

# Disease site mapping
_DISEASE_MAP = {
    "ENDO": "endometrial_carcinoma",
    "UTSARC": "uterine_sarcoma",
    "UN": "uterine_neoplasms",
    "VAG": "vaginal_cancer",
    "VULVA": "vulvar_cancer",
    "VM": "vulvovaginal_melanoma",
    "OV": "ovarian_cancer",
    "LCOC": "less_common_ovarian_cancers",
    "CERV": "cervical_cancer",
    "GTN": "gestational_trophoblastic_neoplasia",
    "HM": "hydatidiform_mole",
    "EB": "evidence_blocks",
    "ST": "staging",
}

# Guideline name detection from first pages
_GUIDELINE_NAMES = {
    "uterine": "Uterine Neoplasms",
    "vaginal": "Vaginal Cancer",
    "vulvar": "Vulvar Cancer",
    "ovarian": "Ovarian Cancer",
    "ovarian_blocks": "Ovarian Cancer Evidence Blocks",
    "cervical": "Cervical Cancer",
    "cervical_blocks": "Cervical Cancer Evidence Blocks",
    "gtn": "Gestational Trophoblastic Neoplasia",
    "gtn_blocks": "Gestational Trophoblastic Neoplasia Evidence Blocks",
}


# ---------------------------------------------------------------------------
# Page classification
# ---------------------------------------------------------------------------
def extract_page_code(page: pymupdf.Page) -> tuple[str | None, str]:
    """Extract NCCN page code from bottom portion of page.

    Returns (page_code, content_type) e.g. ("ENDO-1", "algorithm") or (None, "unknown").
    """
    # Get text from bottom 15% of the page where codes live
    rect = page.rect
    bottom_rect = pymupdf.Rect(rect.x0, rect.y1 * 0.85, rect.x1, rect.y1)
    bottom_text = page.get_text("text", clip=bottom_rect)  # type: ignore[attr-defined]

    # Also check right side for page codes (some NCCN pages put them bottom-right)
    right_rect = pymupdf.Rect(rect.x1 * 0.7, rect.y1 * 0.8, rect.x1, rect.y1)
    right_text = page.get_text("text", clip=right_rect)  # type: ignore[attr-defined]

    combined = bottom_text + "\n" + right_text

    # Try algorithm code first (e.g., ENDO-1, VULVA-10)
    m = _ALGO_CODE_RE.search(combined)
    if m:
        code = f"{m.group(1)}-{m.group(2)}"
        return code, "algorithm"

    # Try principles code (e.g., ENDO-A, VAG-D 2 of 4)
    m = _PRINCIPLES_CODE_RE.search(combined)
    if m:
        suffix = m.group(3) or ""
        code = f"{m.group(1)}-{m.group(2)}"
        if suffix:
            # e.g., "ENDO-A 2 of 4" → "ENDO-A_2of4"
            code += f" {suffix.strip()}"
        return code, "principles"

    # Staging
    m = _STAGING_CODE_RE.search(combined)
    if m:
        return f"ST-{m.group(1)}", "staging"

    # Discussion
    m = _DISCUSSION_CODE_RE.search(combined)
    if m:
        return f"MS-{m.group(1)}", "discussion"

    # Abbreviations
    m = _ABBR_CODE_RE.search(combined)
    if m:
        return f"ABBR-{m.group(1)}", "abbreviations"

    # Evidence Blocks definition (EB-DEF)
    m = _EB_DEF_CODE_RE.search(combined)
    if m:
        return "EB-DEF", "evidence_blocks"

    return None, "unknown"


def classify_page_by_content(page: pymupdf.Page) -> str:
    """Fallback classification using drawing density and text block patterns."""
    blocks = page.get_text("dict")["blocks"]  # type: ignore[attr-defined]
    drawings = page.get_drawings()

    text_blocks = [b for b in blocks if b["type"] == 0]
    drawing_count = len(drawings)

    # Algorithm pages: many drawings (arrows, boxes) + many small text blocks
    if drawing_count > 30 and len(text_blocks) > 10:
        return "algorithm"

    return "text"


def get_disease_from_code(page_code: str) -> str:
    """Map page code prefix to disease site."""
    prefix = page_code.split("-")[0]
    return _DISEASE_MAP.get(prefix, "unknown")


# ---------------------------------------------------------------------------
# PyMuPDF: Spatial extraction for algorithm pages
# ---------------------------------------------------------------------------
def extract_algorithm_geometry(page: pymupdf.Page, page_num: int) -> dict:
    """Extract spatial text blocks and vector drawings from an algorithm page.

    Returns structured geometry for LLM-based flowchart reconstruction.
    """
    text_blocks = []
    raw_dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)  # type: ignore[attr-defined]

    for block in raw_dict["blocks"]:
        if block["type"] != 0:
            continue
        block_text_parts = []
        block_bbox = [block["bbox"][0], block["bbox"][1], block["bbox"][2], block["bbox"][3]]
        is_bold = False
        font_size = 0
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if text:
                    block_text_parts.append(text)
                    font_size = max(font_size, span["size"])
                    if "Bold" in span.get("font", "") or "bold" in span.get("font", ""):
                        is_bold = True

        block_text = " ".join(block_text_parts)
        if block_text and len(block_text) > 1:
            text_blocks.append({
                "text": block_text,
                "x0": round(block_bbox[0], 1),
                "y0": round(block_bbox[1], 1),
                "x1": round(block_bbox[2], 1),
                "y1": round(block_bbox[3], 1),
                "font_size": round(font_size, 1),
                "is_bold": is_bold,
            })

    # Render page as PNG for vision model
    mat = pymupdf.Matrix(2, 2)  # 2x = 144 DPI
    pix = page.get_pixmap(matrix=mat)  # type: ignore[attr-defined]
    image_bytes = pix.tobytes("png")

    return {
        "page_num": page_num,
        "page_width": round(page.rect.width, 1),
        "page_height": round(page.rect.height, 1),
        "text_blocks": text_blocks,
        "image_bytes": image_bytes,
    }


def extract_page_title(page: pymupdf.Page) -> str:
    """Extract the main title from the top portion of a page."""
    rect = page.rect
    # Title is usually in the top 20%, below the NCCN header bar
    top_rect = pymupdf.Rect(rect.x0, rect.y0 + 60, rect.x1, rect.y0 + 150)
    text = page.get_text("text", clip=top_rect).strip()  # type: ignore[attr-defined]
    # Clean up multiple lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # Skip NCCN header lines
    filtered = [l for l in lines if not l.startswith("NCCN") and not l.startswith("Version")
                and not l.startswith("PLEASE NOTE") and not l.startswith("Printed by")
                and "Guidelines" not in l and "Table of Contents" not in l
                and "Discussion" not in l and "NCCN Guidelines Index" not in l]
    return " — ".join(filtered[:2]) if filtered else ""


def extract_footnotes_from_page(page: pymupdf.Page) -> dict[str, str]:
    """Extract footnotes from the bottom portion of an NCCN page.

    Footnotes appear as superscript letters (a, b, c...) followed by text.
    """
    rect = page.rect
    # Footnotes typically in bottom 25% of page
    bottom_rect = pymupdf.Rect(rect.x0, rect.y1 * 0.72, rect.x1, rect.y1 * 0.95)
    text = page.get_text("text", clip=bottom_rect).strip()  # type: ignore[attr-defined]

    footnotes = {}
    # Match patterns like: a Text of footnote  or  a See Principles...
    pattern = re.compile(r"^([a-z])\s+(.+?)(?=\n[a-z]\s|\Z)", re.MULTILINE | re.DOTALL)
    for m in pattern.finditer(text):
        key = m.group(1)
        value = m.group(2).strip().replace("\n", " ")
        # Skip if it looks like a page code or header
        if len(value) > 10 and not value.startswith("Version"):
            footnotes[key] = value

    return footnotes


def extract_cross_references(text: str) -> list[str]:
    """Find NCCN page cross-references in text (e.g., 'See ENDO-4', '(VAG-A)')."""
    refs = set()
    pattern = re.compile(rf"({_ALL_GROUP})-(\d+[A-Z]?|[A-Z]|DEF)")
    for m in pattern.finditer(text):
        refs.add(f"{m.group(1)}-{m.group(2)}")
    return sorted(refs)


# ---------------------------------------------------------------------------
# GPT-4o vision: Reconstruct algorithm flowcharts
# ---------------------------------------------------------------------------
ALGORITHM_SYSTEM_PROMPT = """\
You are an expert at reading NCCN oncology clinical guideline algorithm pages.
These pages show clinical decision trees with boxes containing text connected by arrows.
The flow is generally LEFT to RIGHT: starting conditions on the left, workup/decisions in the middle, and treatment/outcomes on the right.

You will receive:
1. A rendered image of the NCCN guideline algorithm page
2. A list of text blocks extracted from the PDF with their spatial coordinates (x0,y0,x1,y1 in points)

Your task: Convert the algorithm into structured markdown that preserves the decision tree logic.

Rules:
- Read the flowchart LEFT to RIGHT, following arrows
- Use markdown headers (##, ###) for major sections/columns
- Use bullet points and indentation to show branching
- Use → (arrow) to indicate flow between steps
- Capture ALL text exactly as shown (do not paraphrase)
- Preserve footnote superscript references (a, b, c, etc.) inline
- Note cross-references to other pages (e.g., "See ENDO-4", "(VULVA-A)")
- At the end, list all footnotes with their full text
- Include a "Cross-references" section listing all referenced NCCN pages

Output well-structured markdown only. No JSON, no code blocks."""

ALGORITHM_STRUCTURED_PROMPT = """\
You are an expert at reading NCCN oncology clinical guideline algorithm pages.

You will receive a rendered image of an NCCN algorithm page plus extracted text blocks with coordinates.

Extract the algorithm as a JSON object with this EXACT structure:
{
  "title": "Page title (e.g., Disease Limited to the Uterus - Primary Treatment)",
  "columns": ["Column header 1", "Column header 2", ...],
  "nodes": [
    {
      "id": "n1",
      "type": "entry|decision|treatment|evaluation|surveillance|cross_ref",
      "text": "Full text content of this node",
      "column": 0
    }
  ],
  "edges": [
    {
      "from": "n1",
      "to": "n2",
      "label": "condition or empty string"
    }
  ],
  "footnotes": {
    "a": "Full footnote text",
    "b": "Full footnote text"
  },
  "cross_references": ["ENDO-4", "ENDO-A"]
}

Rules:
- Read LEFT to RIGHT following arrows
- Every text box = one node
- Every arrow = one edge
- Capture ALL text exactly (no paraphrasing)
- Include footnote markers in node text (e.g., "TH/BSO^c and surgical staging^d,e")
- cross_ref nodes point to other NCCN pages (e.g., "See ENDO-4")
- Return ONLY valid JSON, no markdown or explanation"""


def reconstruct_algorithm_with_vision(
    geometry: dict,
    page_code: str,
    client,
    deployment: str,
) -> dict:
    """Send algorithm page image + text coordinates to GPT-4o for reconstruction."""
    # Compact text block summary with spatial info
    blocks_summary = []
    for tb in geometry["text_blocks"]:
        blocks_summary.append({
            "text": tb["text"],
            "x_pct": round(tb["x0"] / geometry["page_width"] * 100, 1),
            "y_pct": round(tb["y0"] / geometry["page_height"] * 100, 1),
            "bold": tb["is_bold"],
        })

    image_b64 = base64.b64encode(geometry["image_bytes"]).decode()

    # First call: get structured markdown
    messages_md = [
        {"role": "system", "content": ALGORITHM_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{image_b64}",
                "detail": "high",
            }},
            {"type": "text", "text": (
                f"Page code: {page_code}\n\n"
                f"Extracted text blocks (sorted by position):\n"
                f"{json.dumps(blocks_summary, indent=2)}\n\n"
                "Convert this NCCN algorithm page into structured markdown."
            )},
        ]},
    ]

    # Second call: get structured JSON decision tree
    messages_json = [
        {"role": "system", "content": ALGORITHM_STRUCTURED_PROMPT},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{image_b64}",
                "detail": "high",
            }},
            {"type": "text", "text": (
                f"Page code: {page_code}\n\n"
                f"Text blocks:\n{json.dumps(blocks_summary, indent=2)}\n\n"
                "Extract as JSON."
            )},
        ]},
    ]

    logger.info("  Calling GPT-4o vision for markdown extraction...")
    resp_md = client.chat.completions.create(
        model=deployment,
        messages=messages_md,
        temperature=0,
        max_tokens=4096,
    )
    markdown = resp_md.choices[0].message.content.strip()

    logger.info("  Calling GPT-4o vision for structured JSON extraction...")
    resp_json = client.chat.completions.create(
        model=deployment,
        messages=messages_json,
        temperature=0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    raw_json = resp_json.choices[0].message.content.strip()

    try:
        decision_tree = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.warning("  Failed to parse JSON from vision model, storing raw text")
        decision_tree = {"raw": raw_json}

    return {
        "markdown": markdown,
        "decision_tree": decision_tree,
    }


# ---------------------------------------------------------------------------
# Docling: Extract tables and text from non-algorithm pages
# ---------------------------------------------------------------------------
def extract_with_docling(pdf_path: Path) -> dict:
    """Run Docling on the full PDF for text and table extraction.

    Returns a dict keyed by 1-based page number with markdown and tables.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    logger.info("Running Docling on %s (this may take a few minutes)...", pdf_path.name)

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False  # NCCN PDFs are digitally native
    pipeline_options.do_table_structure = True
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )

    result = converter.convert(str(pdf_path))
    doc = result.document

    # Get full markdown
    full_markdown = doc.export_to_markdown()

    # Get tables with provenance
    tables = []
    for table in doc.tables:
        table_data: dict[str, Any] = {
            "markdown": table.export_to_markdown(),
        }
        if table.prov:
            prov = table.prov[0]
            table_data["page_num"] = prov.page_no
        try:
            df = table.export_to_dataframe()
            table_data["headers"] = list(df.columns)
            table_data["rows"] = df.values.tolist()
        except Exception:
            pass
        tables.append(table_data)

    logger.info("  Docling extracted %d tables, %d chars of markdown",
                len(tables), len(full_markdown))

    return {
        "full_markdown": full_markdown,
        "tables": tables,
    }


# ---------------------------------------------------------------------------
# Detect guideline metadata from PDF
# ---------------------------------------------------------------------------
def detect_guideline_info(pdf_path: Path) -> dict:
    """Extract guideline name, version, and date from the cover page."""
    doc = pymupdf.open(str(pdf_path))
    # Read first 3 pages to find metadata
    cover_text = ""
    for i in range(min(3, len(doc))):
        cover_text += doc[i].get_text("text") + "\n"  # type: ignore[attr-defined]
    doc.close()

    # Extract version
    version_match = re.search(r"Version\s+(\d+\.\d{4})", cover_text)
    version = version_match.group(1) if version_match else "unknown"

    # Extract date
    date_match = re.search(
        r"(?:Version\s+\d+\.\d{4}\s*(?:—|–|-)\s*)([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
        cover_text,
    )
    version_date = date_match.group(1) if date_match else ""

    # Detect guideline name
    name = "Unknown"
    fname = pdf_path.stem.lower()
    for key, gname in _GUIDELINE_NAMES.items():
        if key in fname:
            name = gname
            break
    # Also try from text
    if "Uterine Neoplasms" in cover_text:
        name = "Uterine Neoplasms"
    elif "Vaginal Cancer" in cover_text:
        name = "Vaginal Cancer"
    elif "Vulvar Cancer" in cover_text:
        name = "Vulvar Cancer"
    elif "Ovarian Cancer" in cover_text:
        if "Evidence Blocks" in cover_text:
            name = "Ovarian Cancer Evidence Blocks"
        else:
            name = "Ovarian Cancer"
    elif "Cervical Cancer" in cover_text:
        if "Evidence Blocks" in cover_text:
            name = "Cervical Cancer Evidence Blocks"
        else:
            name = "Cervical Cancer"
    elif "Gestational Trophoblastic" in cover_text:
        if "Evidence Blocks" in cover_text:
            name = "Gestational Trophoblastic Neoplasia Evidence Blocks"
        else:
            name = "Gestational Trophoblastic Neoplasia"

    return {
        "guideline_name": name,
        "version": version,
        "version_date": version_date,
        "source_pdf": pdf_path.name,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def process_pdf(
    pdf_path: Path,
    output_path: Path | None,
    openai_client=None,
    openai_deployment: str = "gpt-4o",
    skip_vision: bool = False,
) -> dict:
    """Process a single NCCN guideline PDF into structured JSON."""
    logger.info("=" * 60)
    logger.info("Processing: %s", pdf_path.name)
    logger.info("=" * 60)

    # Step 1: Detect guideline metadata
    info = detect_guideline_info(pdf_path)
    logger.info("Guideline: %s v%s (%s)", info["guideline_name"], info["version"], info["version_date"])

    # Step 2: Classify all pages with PyMuPDF
    doc = pymupdf.open(str(pdf_path))
    page_count = len(doc)
    logger.info("Total pages: %d", page_count)

    pages_classified = []
    for i in range(page_count):
        page = doc[i]
        code, content_type = extract_page_code(page)

        # Fallback classification if no code found
        if content_type == "unknown":
            content_type = classify_page_by_content(page)

        pages_classified.append({
            "page_num": i + 1,  # 1-based
            "page_code": code,
            "content_type": content_type,
        })

    # Count by type
    type_counts = {}
    for p in pages_classified:
        t = p["content_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    logger.info("Page classification: %s", type_counts)

    # Step 3: Extract algorithm pages with PyMuPDF + optional GPT-4o vision
    algorithm_pages = [p for p in pages_classified if p["content_type"] == "algorithm"]
    processed_pages = []

    for pg in algorithm_pages:
        page_idx = pg["page_num"] - 1
        page = doc[page_idx]
        page_code = pg["page_code"] or f"page_{pg['page_num']}"

        logger.info("Processing algorithm page %d: %s", pg["page_num"], page_code)

        title = extract_page_title(page)
        footnotes = extract_footnotes_from_page(page)
        geometry = extract_algorithm_geometry(page, pg["page_num"])

        # Get full page text for cross-reference extraction
        full_text = page.get_text("text")  # type: ignore[attr-defined]
        cross_refs = extract_cross_references(full_text)
        # Remove self-reference
        cross_refs = [r for r in cross_refs if r != page_code]

        page_data = {
            "page_code": page_code,
            "page_num": pg["page_num"],
            "content_type": "algorithm",
            "disease": get_disease_from_code(page_code),
            "title": title,
            "footnotes": footnotes,
            "cross_references": cross_refs,
        }

        if openai_client and not skip_vision:
            try:
                vision_result = reconstruct_algorithm_with_vision(
                    geometry, page_code, openai_client, openai_deployment,
                )
                page_data["markdown"] = vision_result["markdown"]
                page_data["decision_tree"] = vision_result["decision_tree"]
            except Exception as e:
                logger.error("  Vision extraction failed for %s: %s", page_code, e)
                # Fallback: use raw text blocks as markdown
                raw_text = "\n".join(tb["text"] for tb in geometry["text_blocks"])
                page_data["markdown"] = f"## {page_code}: {title}\n\n{raw_text}"
                page_data["decision_tree"] = None
        else:
            # No vision — store raw text blocks
            raw_text = "\n".join(tb["text"] for tb in geometry["text_blocks"])
            page_data["markdown"] = f"## {page_code}: {title}\n\n{raw_text}"
            page_data["decision_tree"] = None

        processed_pages.append(page_data)

    doc.close()

    # Step 4: Extract text/table pages with Docling
    docling_result = extract_with_docling(pdf_path)

    # Step 5: Process non-algorithm pages
    non_algo_pages = [p for p in pages_classified
                      if p["content_type"] != "algorithm" and p["page_code"] is not None]

    # Re-open PDF for non-algo page processing
    doc = pymupdf.open(str(pdf_path))

    for pg in non_algo_pages:
        page_idx = pg["page_num"] - 1
        page = doc[page_idx]
        page_code = pg["page_code"]

        logger.info("Processing %s page %d: %s", pg["content_type"], pg["page_num"], page_code)

        title = extract_page_title(page)
        full_text = page.get_text("text")  # type: ignore[attr-defined]
        footnotes = extract_footnotes_from_page(page)
        cross_refs = extract_cross_references(full_text)
        cross_refs = [r for r in cross_refs if r != page_code]

        # Find matching tables from Docling
        matching_tables = []
        for t in docling_result.get("tables", []):
            if t.get("page_num") == pg["page_num"]:
                matching_tables.append(t)

        page_data = {
            "page_code": page_code,
            "page_num": pg["page_num"],
            "content_type": pg["content_type"],
            "disease": get_disease_from_code(page_code),
            "title": title,
            "markdown": full_text.strip(),  # PyMuPDF text as fallback
            "footnotes": footnotes,
            "cross_references": cross_refs,
        }

        if matching_tables:
            page_data["tables"] = matching_tables
            page_data["content_type"] = "table"

        processed_pages.append(page_data)

    doc.close()

    # Sort by page number
    processed_pages.sort(key=lambda p: p["page_num"])

    # Build output
    output = {
        "guideline_name": info["guideline_name"],
        "version": info["version"],
        "version_date": info["version_date"],
        "source_pdf": info["source_pdf"],
        "processed_date": datetime.now().strftime("%Y-%m-%d"),
        "page_count": page_count,
        "pages": processed_pages,
    }

    # Step 6: Write JSON output
    if output_path is None:
        safe_name = pdf_path.stem.lower().replace(" ", "_")
        output_path = DEFAULT_OUTPUT_DIR / f"{safe_name}_v{info['version']}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Output written to: %s", output_path)
    logger.info("Processed %d pages (%d algorithm, %d other)",
                len(processed_pages),
                sum(1 for p in processed_pages if p["content_type"] == "algorithm"),
                sum(1 for p in processed_pages if p["content_type"] != "algorithm"))

    return output


def update_manifest(output_dir: Path, guideline_info: dict):
    """Update manifest.json with the processed guideline info."""
    manifest_path = output_dir / "manifest.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {"guidelines": []}

    # Remove existing entry for same guideline
    manifest["guidelines"] = [
        g for g in manifest["guidelines"]
        if g.get("source_pdf") != guideline_info["source_pdf"]
    ]

    manifest["guidelines"].append({
        "guideline_name": guideline_info["guideline_name"],
        "version": guideline_info["version"],
        "version_date": guideline_info["version_date"],
        "source_pdf": guideline_info["source_pdf"],
        "processed_date": datetime.now().strftime("%Y-%m-%d"),
        "json_file": f"{Path(guideline_info['source_pdf']).stem.lower()}_v{guideline_info['version']}.json",
    })

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Updated manifest: %s", manifest_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Process NCCN guideline PDFs into structured JSON for the ClinicalGuidelines agent."
    )
    parser.add_argument(
        "--pdf", type=str, required=True, action="append",
        help="Path to NCCN PDF file (can specify multiple times)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON path (default: data/nccn_guidelines/<name>_v<version>.json)",
    )
    parser.add_argument(
        "--skip-vision", action="store_true",
        help="Skip GPT-4o vision calls for algorithm pages (use raw text extraction only)",
    )
    parser.add_argument(
        "--deployment", type=str, default=None,
        help="Azure OpenAI deployment name for vision model (default: from .env or 'gpt-4o')",
    )
    args = parser.parse_args()

    # Set up OpenAI client
    openai_client = None
    deployment = args.deployment or "gpt-4o"

    if not args.skip_vision:
        try:
            from openai import AzureOpenAI

            # Load .env from src/
            env_path = REPO_ROOT / "src" / ".env"
            if env_path.exists():
                from dotenv import load_dotenv
                load_dotenv(env_path)

            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")

            if endpoint:
                client_kwargs: dict[str, Any] = {
                    "azure_endpoint": endpoint,
                    "api_version": "2024-12-01-preview",
                }
                if api_key:
                    client_kwargs["api_key"] = api_key
                else:
                    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
                    credential = DefaultAzureCredential()
                    token_provider = get_bearer_token_provider(
                        credential, "https://cognitiveservices.azure.com/.default"
                    )
                    client_kwargs["azure_ad_token_provider"] = token_provider

                openai_client = AzureOpenAI(**client_kwargs)
                logger.info("Azure OpenAI client initialized (deployment: %s)", deployment)
            else:
                logger.warning("No AZURE_OPENAI_ENDPOINT found — skipping vision extraction")
        except ImportError:
            logger.warning("openai package not installed — skipping vision extraction")
        except Exception as e:
            logger.warning("Failed to init OpenAI client: %s — skipping vision", e)

    # Process each PDF
    for pdf_str in args.pdf:
        pdf_path = Path(pdf_str).resolve()
        if not pdf_path.exists():
            # Try relative to repo parent (where PDFs typically live)
            alt_path = REPO_ROOT.parent / pdf_str
            if alt_path.exists():
                pdf_path = alt_path
            else:
                logger.error("PDF not found: %s", pdf_str)
                continue

        output_path = Path(args.output) if args.output else None

        start = time.time()
        result = process_pdf(
            pdf_path=pdf_path,
            output_path=output_path,
            openai_client=openai_client,
            openai_deployment=deployment,
            skip_vision=args.skip_vision,
        )
        elapsed = time.time() - start

        # Update manifest
        update_manifest(DEFAULT_OUTPUT_DIR, result)

        logger.info("Done in %.1fs", elapsed)


if __name__ == "__main__":
    main()
