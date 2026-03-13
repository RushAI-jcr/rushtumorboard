#!/usr/bin/env python3
"""Generate the GYN Tumor Board PPTX template programmatically.

Produces tumor_board_slides.pptx with 3 slide layouts:
  Layout 0 — Patient Overview (title + subtitle + 6-bullet body)
  Layout 1 — Clinical Findings (two-column: bullets left, chart right)
  Layout 2 — Treatment & Trials (full-width bullets)

Run: python scripts/generate_pptx_template.py
Output: src/scenarios/default/templates/tumor_board_slides.pptx
"""

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Medical color palette
NAVY = RGBColor(0x1B, 0x36, 0x5D)
TEAL = RGBColor(0x00, 0x7C, 0x91)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF5, 0xF5, 0xF5)
DARK_TEXT = RGBColor(0x33, 0x33, 0x33)

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def _set_slide_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(slide, left, top, width, height, text="", font_size=14,
                 bold=False, color=DARK_TEXT, alignment=PP_ALIGN.LEFT, name=None):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    if name:
        txBox.name = name
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = alignment
    return txBox


def create_template():
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    # ── Slide 1: Patient Overview ──
    slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    _set_slide_bg(slide1, WHITE)

    # Navy header bar
    header = slide1.shapes.add_shape(
        1, Inches(0), Inches(0), SLIDE_WIDTH, Inches(1.4)  # MSO_SHAPE.RECTANGLE = 1
    )
    header.fill.solid()
    header.fill.fore_color.rgb = NAVY
    header.line.fill.background()
    header.name = "header_bar"

    # Title (white on navy)
    _add_textbox(slide1, Inches(0.8), Inches(0.2), Inches(11), Inches(0.6),
                 text="Patient Overview", font_size=32, bold=True, color=WHITE,
                 name="title")

    # Subtitle (teal on navy)
    _add_textbox(slide1, Inches(0.8), Inches(0.8), Inches(11), Inches(0.5),
                 text="FIGO Stage | Molecular Profile | Date",
                 font_size=18, color=TEAL, name="subtitle")

    # Teal accent line
    line = slide1.shapes.add_shape(
        1, Inches(0.8), Inches(1.6), Inches(1.5), Inches(0.05)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = TEAL
    line.line.fill.background()

    # Bullet area
    _add_textbox(slide1, Inches(0.8), Inches(1.9), Inches(11.5), Inches(5.0),
                 text="", font_size=16, name="body")

    # Footer
    _add_textbox(slide1, Inches(0.8), Inches(7.0), Inches(11.5), Inches(0.4),
                 text="GYN Oncology Tumor Board", font_size=10,
                 color=RGBColor(0x99, 0x99, 0x99), alignment=PP_ALIGN.CENTER,
                 name="footer")

    # ── Slide 2: Clinical Findings (two-column) ──
    slide2 = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide2, WHITE)

    # Header bar
    header2 = slide2.shapes.add_shape(
        1, Inches(0), Inches(0), SLIDE_WIDTH, Inches(1.2)
    )
    header2.fill.solid()
    header2.fill.fore_color.rgb = NAVY
    header2.line.fill.background()

    _add_textbox(slide2, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 text="Clinical Findings", font_size=28, bold=True, color=WHITE,
                 name="title")

    # Left column — bullets
    _add_textbox(slide2, Inches(0.8), Inches(1.5), Inches(6.0), Inches(5.5),
                 text="", font_size=14, name="body_left")

    # Right column — chart area (placeholder text)
    chart_box = _add_textbox(slide2, Inches(7.5), Inches(1.5), Inches(5.3), Inches(0.4),
                              text="Tumor Marker Trend", font_size=14, bold=True,
                              color=TEAL, alignment=PP_ALIGN.CENTER, name="chart_title")

    # Chart image placeholder (light gray box)
    chart_placeholder = slide2.shapes.add_shape(
        1, Inches(7.5), Inches(2.0), Inches(5.3), Inches(4.5)
    )
    chart_placeholder.fill.solid()
    chart_placeholder.fill.fore_color.rgb = LIGHT_GRAY
    chart_placeholder.line.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
    chart_placeholder.name = "chart_area"

    # Footer
    _add_textbox(slide2, Inches(0.8), Inches(7.0), Inches(11.5), Inches(0.4),
                 text="GYN Oncology Tumor Board", font_size=10,
                 color=RGBColor(0x99, 0x99, 0x99), alignment=PP_ALIGN.CENTER,
                 name="footer")

    # ── Slide 3: Treatment & Trials ──
    slide3 = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide3, WHITE)

    header3 = slide3.shapes.add_shape(
        1, Inches(0), Inches(0), SLIDE_WIDTH, Inches(1.2)
    )
    header3.fill.solid()
    header3.fill.fore_color.rgb = NAVY
    header3.line.fill.background()

    _add_textbox(slide3, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 text="Treatment Plan & Clinical Trials", font_size=28,
                 bold=True, color=WHITE, name="title")

    # Teal divider
    div = slide3.shapes.add_shape(
        1, Inches(0.8), Inches(1.35), Inches(1.5), Inches(0.05)
    )
    div.fill.solid()
    div.fill.fore_color.rgb = TEAL
    div.line.fill.background()

    # Main body
    _add_textbox(slide3, Inches(0.8), Inches(1.6), Inches(11.5), Inches(3.5),
                 text="", font_size=14, name="body")

    # Trials section header
    _add_textbox(slide3, Inches(0.8), Inches(5.2), Inches(11.5), Inches(0.4),
                 text="Eligible Clinical Trials", font_size=16, bold=True,
                 color=TEAL, name="trials_header")

    # Trials body
    _add_textbox(slide3, Inches(0.8), Inches(5.7), Inches(11.5), Inches(1.2),
                 text="", font_size=13, name="trials_body")

    # Footer
    _add_textbox(slide3, Inches(0.8), Inches(7.0), Inches(11.5), Inches(0.4),
                 text="GYN Oncology Tumor Board", font_size=10,
                 color=RGBColor(0x99, 0x99, 0x99), alignment=PP_ALIGN.CENTER,
                 name="footer")

    return prs


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    output_path = os.path.join(
        repo_root, "src", "scenarios", "default", "templates", "tumor_board_slides.pptx"
    )

    prs = create_template()
    prs.save(output_path)
    print(f"Template saved to: {output_path}")


if __name__ == "__main__":
    main()
