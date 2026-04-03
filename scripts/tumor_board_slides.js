#!/usr/bin/env node
/**
 * GYN Tumor Board — 5-Slide PptxGenJS Generator
 * Mirrors the Rush University Medical Center 5-column tumor board handout.
 * One slide per column: Patient | Diagnosis | Prev Tx | Imaging | Discussion
 *
 * Usage:
 *   echo '{ "slides": {...}, "tumor_markers_raw": [...], "output_path": "out.pptx" }' \
 *     | node scripts/tumor_board_slides.js
 */

"use strict";

const pptxgen = require("pptxgenjs");

// ── Color palette (matches Word doc + AI polish) ───────────────────────────────
const NAVY      = "1B365D";   // header/footer bar
const TEAL      = "007C91";   // primary accent
const TEAL_DIM  = "4E95A8";   // muted teal for subtitles, badges
const TEAL_BG   = "EBF7FA";   // chip background
const RED       = "FF0000";   // staging/genetics (matches REDTEXT in real handout)
const RED_BG    = "FEF2F2";   // light red staging panel fill
const RED_RULE  = "F5B8B8";   // light red rule
const WHITE     = "FFFFFF";
const OFF_WHITE = "F8FAFC";   // card background
const DARK      = "1C2B3A";   // body text
const MUTED     = "56687A";   // labels, secondary
const SUBTLE    = "8FA3B0";   // footer text
const RULE      = "CDD8E0";   // thin dividers
const FONT      = "Calibri";

// ── Layout: LAYOUT_WIDE = 13.333" × 7.5" ──────────────────────────────────────
const W        = 13.333;
const H        = 7.5;
const HDR_H    = 1.02;         // navy header height
const MARGIN   = 0.52;
const BODY_Y   = HDR_H + 0.20; // 1.22"
const FTR_H    = 0.36;
const BODY_H   = H - BODY_Y - FTR_H - 0.06;  // ~5.86"

// ── Base slide frame ───────────────────────────────────────────────────────────

function frame(prs, slide, titleText, subtitleText, slideNum) {
  // Navy header bar
  slide.addShape(prs.ShapeType.rect, {
    x: 0, y: 0, w: W, h: HDR_H,
    fill: { color: NAVY }, line: { color: NAVY },
  });
  // Teal accent stripe at the bottom of the header
  slide.addShape(prs.ShapeType.rect, {
    x: 0, y: HDR_H - 0.05, w: W, h: 0.05,
    fill: { color: TEAL }, line: { color: TEAL },
  });

  // Slide title
  const titleFontSize = titleText.length > 38 ? 23 : titleText.length > 28 ? 26 : 30;
  const titleY = subtitleText ? 0.08 : 0.17;
  const titleH = subtitleText ? 0.52 : 0.70;
  slide.addText(titleText, {
    x: MARGIN, y: titleY, w: W - MARGIN * 2 - 1.3, h: titleH,
    fontFace: FONT, fontSize: titleFontSize, bold: true, color: WHITE,
    margin: 0, valign: "middle",
  });

  // Subtitle (e.g. "Tumor Markers" on slide 3 when labs present)
  if (subtitleText) {
    slide.addText(subtitleText, {
      x: MARGIN, y: 0.62, w: W - MARGIN * 2 - 1.3, h: 0.30,
      fontFace: FONT, fontSize: 10.5, color: TEAL_DIM,
      margin: 0, valign: "top",
    });
  }

  // Slide number badge (top-right of header)
  slide.addText(`${slideNum} / 5`, {
    x: W - 1.25, y: 0.19, w: 1.05, h: 0.34,
    fontFace: FONT, fontSize: 10, bold: true, color: TEAL_DIM,
    margin: 0, align: "right", valign: "middle",
  });

  // Navy footer bar
  slide.addShape(prs.ShapeType.rect, {
    x: 0, y: H - FTR_H, w: W, h: FTR_H,
    fill: { color: NAVY }, line: { color: NAVY },
  });
  slide.addText("GYN Oncology Tumor Board  ·  Rush University Medical Center", {
    x: MARGIN, y: H - FTR_H + 0.05, w: W - MARGIN * 2, h: FTR_H - 0.08,
    fontFace: FONT, fontSize: 8.5, color: SUBTLE,
    margin: 0, align: "center", valign: "middle",
  });
}

// ── Drawing helpers ────────────────────────────────────────────────────────────

function hRule(prs, slide, y, color = RULE) {
  slide.addShape(prs.ShapeType.rect, {
    x: MARGIN, y, w: W - MARGIN * 2, h: 0.02,
    fill: { color }, line: { color },
  });
}

function vRule(prs, slide, x, y, h) {
  slide.addShape(prs.ShapeType.rect, {
    x, y, w: 0.016, h,
    fill: { color: RULE }, line: { color: RULE },
  });
}

// ── Text-run builders ──────────────────────────────────────────────────────────

/**
 * Bullet list → PptxGenJS rich-text array.
 * Uses real bullet character (not unicode prefix to avoid doubles).
 */
function mkBullets(items, { size = 13, color = DARK, maxItems = 20, gap = 5 } = {}) {
  return items.slice(0, maxItems).map((txt, i) => ({
    text: txt,
    options: {
      bullet: true,
      breakLine: i < Math.min(items.length, maxItems) - 1,
      fontFace: FONT, fontSize: size, color,
      paraSpaceAfter: gap,
    },
  }));
}

/**
 * Split "Label: value" strings into bold-muted label + dark value runs.
 * Falls back to plain text for strings without ": ".
 */
function mkLabelValue(items) {
  const size = 15, gap = 11;
  return items.flatMap((txt, i) => {
    const sep = txt.indexOf(": ");
    const last = i === items.length - 1;
    if (sep > -1) {
      return [
        { text: txt.slice(0, sep + 1) + "  ", options: { bold: true,  fontFace: FONT, fontSize: size, color: MUTED,  breakLine: false } },
        { text: txt.slice(sep + 2),            options: { bold: false, fontFace: FONT, fontSize: size, color: DARK,   breakLine: !last,  paraSpaceAfter: gap } },
      ];
    }
    return [{ text: txt, options: { fontFace: FONT, fontSize: size, color: DARK, breakLine: !last, paraSpaceAfter: gap } }];
  });
}

/**
 * Staging/genetics runs: bold label + value, all in RED.
 */
function mkStagingRuns(pairs) {
  return pairs.flatMap(([label, value], i) => [
    { text: label + "  ", options: { bold: true,  fontFace: FONT, fontSize: 13, color: RED, breakLine: false } },
    { text: value,        options: { bold: false, fontFace: FONT, fontSize: 13, color: RED, breakLine: i < pairs.length - 1, paraSpaceAfter: 6 } },
  ]);
}

// ── Slide 1: Patient (Col 0) ───────────────────────────────────────────────────
//
// Mirrors the Patient column of the real handout:
// Case #, Last name, MRN, Attending, Inpt flag, RTC, Location, Path date, CA-125 trend.
// Rendered as a structured card with bold-label / value rows.

function buildSlide1(prs, sc) {
  const slide = prs.addSlide();
  frame(prs, slide, sc.patient_title || "Patient", "", 1);

  const items = sc.patient_bullets || [];
  if (items.length === 0) return;

  // Card background
  slide.addShape(prs.ShapeType.rect, {
    x: MARGIN, y: BODY_Y, w: W - MARGIN * 2, h: BODY_H,
    fill: { color: OFF_WHITE }, line: { color: RULE },
  });
  // Teal left accent stripe on card
  slide.addShape(prs.ShapeType.rect, {
    x: MARGIN, y: BODY_Y, w: 0.07, h: BODY_H,
    fill: { color: TEAL }, line: { color: TEAL },
  });

  slide.addText(mkLabelValue(items), {
    x: MARGIN + 0.22, y: BODY_Y + 0.24,
    w: W - MARGIN * 2 - 0.40, h: BODY_H - 0.44,
    fontFace: FONT, valign: "top",
  });
}

// ── Slide 2: Diagnosis & Pertinent History (Col 1) ─────────────────────────────
//
// Narrative bullets in upper body.
// RED staging panel at bottom — mirrors the REDTEXT style in the real handout.
// Two-column layout for the staging block (Primary Site/Stage | Germline/Somatic).

function buildSlide2(prs, sc) {
  const slide = prs.addSlide();
  frame(prs, slide, sc.diagnosis_title || "Diagnosis & Pertinent History", "", 2);

  const items = sc.diagnosis_bullets || [];
  const stagingPairs = [
    ["Primary Site:", sc.primary_site       || "—"],
    ["Stage:",        sc.stage              || "—"],
    ["Germline:",     sc.germline_genetics  || "Not tested"],
    ["Somatic:",      sc.somatic_genetics   || "—"],
  ];

  const panelH      = 1.80;
  const narrativeH  = BODY_H - panelH - 0.20;

  // Narrative bullets
  if (items.length > 0) {
    slide.addText(mkBullets(items, { size: 13 }), {
      x: MARGIN, y: BODY_Y, w: W - MARGIN * 2, h: narrativeH,
      fontFace: FONT, valign: "top",
    });
  }

  // RED rule above staging panel
  hRule(prs, slide, BODY_Y + narrativeH + 0.06, RED_RULE);

  const panelY = BODY_Y + narrativeH + 0.11;

  // Light red staging panel
  slide.addShape(prs.ShapeType.rect, {
    x: MARGIN, y: panelY, w: W - MARGIN * 2, h: panelH - 0.06,
    fill: { color: RED_BG }, line: { color: RED_RULE },
  });

  // Two-column layout: left = Primary Site + Stage, right = Germline + Somatic
  const halfW = (W - MARGIN * 2) / 2 - 0.18;
  slide.addText(mkStagingRuns(stagingPairs.slice(0, 2)), {
    x: MARGIN + 0.20, y: panelY + 0.16,
    w: halfW, h: panelH - 0.28,
    fontFace: FONT, valign: "top",
  });
  slide.addText(mkStagingRuns(stagingPairs.slice(2)), {
    x: MARGIN + halfW + 0.36, y: panelY + 0.16,
    w: halfW, h: panelH - 0.28,
    fontFace: FONT, valign: "top",
  });
}

// ── Slide 3: Previous Tx or Operative Findings, Tumor Markers (Col 2) ──────────
//
// Title matches real handout column header exactly.
// Treatment history bullets full-width when no lab data.
// When lab data present: two-column — bullets left, native CA-125 line chart right.

function buildSlide3(prs, sc, markersRaw) {
  const parsed = parseMarkers(markersRaw);
  const slide  = prs.addSlide();
  const sub    = parsed ? (sc.findings_chart_title || "Tumor Markers") : "";
  frame(prs, slide, sc.prevtx_title || "Previous Tx or Operative Findings", sub, 3);

  const chartW  = 5.6;
  const chartX  = W - MARGIN - chartW;
  const bulletW = parsed ? W - MARGIN * 2 - chartW - 0.30 : W - MARGIN * 2;
  const items   = sc.prevtx_bullets || [];

  if (items.length > 0) {
    slide.addText(mkBullets(items, { size: 12.5 }), {
      x: MARGIN, y: BODY_Y, w: bulletW, h: BODY_H,
      fontFace: FONT, valign: "top",
    });
  }

  if (parsed) {
    vRule(prs, slide, MARGIN + bulletW + 0.13, BODY_Y, BODY_H);

    const chartTitle = sc.findings_chart_title || "CA-125 Trend";
    slide.addText(chartTitle, {
      x: chartX, y: BODY_Y, w: chartW, h: 0.30,
      fontFace: FONT, fontSize: 12.5, bold: true, color: TEAL,
      align: "center", margin: 0,
    });

    slide.addChart(prs.ChartType.line, [{
      name: chartTitle,
      labels: parsed.labels,
      values: parsed.values,
    }], {
      x: chartX, y: BODY_Y + 0.33, w: chartW, h: BODY_H - 0.36,
      chartColors: [TEAL],
      lineSize: 2.5,
      lineSmooth: false,
      showDatalabels: true,
      dataLabelColor: NAVY,
      dataLabelFontSize: 8,
      catAxisLabelColor: MUTED,
      valAxisLabelColor: MUTED,
      catAxisLabelFontSize: 8,
      valAxisLabelFontSize: 8,
      valGridLine: { color: RULE, size: 0.5 },
      catGridLine: { style: "none" },
      chartArea: { fill: { color: WHITE } },
      plotArea: { fill: { color: WHITE } },
      showLegend: false,
      showTitle: false,
    });
  }
}

// ── Slide 4: Imaging (Col 3) ───────────────────────────────────────────────────
//
// Dated imaging study bullets. Single-column for ≤4 studies; two-column for 5+.

function buildSlide4(prs, sc) {
  const slide = prs.addSlide();
  frame(prs, slide, sc.imaging_title || "Imaging", "", 4);

  const items  = sc.imaging_bullets || [];
  const twoCol = items.length >= 5;
  const half   = Math.ceil(items.length / 2);

  if (!twoCol) {
    if (items.length > 0) {
      slide.addText(mkBullets(items, { size: 13 }), {
        x: MARGIN, y: BODY_Y, w: W - MARGIN * 2, h: BODY_H,
        fontFace: FONT, valign: "top",
      });
    }
  } else {
    const colW = (W - MARGIN * 2 - 0.30) / 2;
    slide.addText(mkBullets(items.slice(0, half), { size: 12.5 }), {
      x: MARGIN, y: BODY_Y, w: colW, h: BODY_H,
      fontFace: FONT, valign: "top",
    });
    vRule(prs, slide, MARGIN + colW + 0.13, BODY_Y, BODY_H);
    slide.addText(mkBullets(items.slice(half), { size: 12.5 }), {
      x: MARGIN + colW + 0.29, y: BODY_Y, w: colW, h: BODY_H,
      fontFace: FONT, valign: "top",
    });
  }
}

// ── Slide 5: Discussion (Col 4) ────────────────────────────────────────────────
//
// Clinical discussion agenda is the primary content.
// Review type + trial eligibility note are a compact header row.
// AI-identified trials are a subtle reference footnote at the bottom.
//
// Layout:
//   [Review chips]  ·  Eligible: [note]       ← compact single row
//   ────────────────────────────────────────
//   [Discussion agenda bullets]               ← PRIMARY — most of the slide
//   ────────────────────────────────────────
//   Trials to consider (AI):  NCT... | NCT…   ← subdued footnote, if present

function buildSlide5(prs, sc) {
  const slide = prs.addSlide();
  frame(prs, slide, sc.discussion_title || "Discussion", "", 5);

  let y = BODY_Y;

  // ── Header row: review chips + eligibility note ───────────────────────────
  const types  = sc.review_types && sc.review_types.length > 0 ? sc.review_types : ["Tx Disc"];
  const CHIP_W = 1.72;
  const CHIP_H = 0.34;
  const CHIP_G = 0.14;
  const chipsW = types.length * CHIP_W + (types.length - 1) * CHIP_G;

  types.forEach((t, i) => {
    const cx = MARGIN + i * (CHIP_W + CHIP_G);
    slide.addShape(prs.ShapeType.rect, {
      x: cx, y, w: CHIP_W, h: CHIP_H,
      fill: { color: TEAL_BG }, line: { color: TEAL },
    });
    slide.addText(t, {
      x: cx, y: y + 0.01, w: CHIP_W, h: CHIP_H,
      fontFace: FONT, fontSize: 11.5, bold: true, color: TEAL,
      align: "center", valign: "middle", margin: 0,
    });
  });

  // Eligibility note — right-aligned inline with chips
  const hasElig = !!(sc.trial_eligible_note && sc.trial_eligible_note.trim());
  const eligX   = MARGIN + chipsW + 0.22;
  const eligW   = W - eligX - MARGIN;
  if (eligW > 0.5) {
    slide.addText(
      hasElig ? `Eligible for trial:  ${sc.trial_eligible_note}` : "Eligible for trial:  —",
      {
        x: eligX, y: y + 0.01, w: eligW, h: CHIP_H,
        fontFace: FONT, fontSize: 11, color: hasElig ? TEAL : SUBTLE,
        bold: false, italic: !hasElig,
        valign: "middle", margin: 0,
      }
    );
  }
  y += CHIP_H + 0.13;

  hRule(prs, slide, y);
  y += 0.14;

  // ── Clinical discussion agenda — primary content ───────────────────────────
  const planItems  = sc.discussion_bullets || [];
  const trialItems = sc.trial_entries      || [];
  const refItems   = (sc.references || []).slice(0, 4);

  // Evidence footnote height — scales with the taller of the two columns
  const trialLines = Math.min(trialItems.length, 3);
  const refLines   = refItems.length;
  const footLines  = trialItems.length > 0 && refItems.length > 0
    ? Math.max(trialLines, refLines)
    : trialLines + refLines;
  const trialsH    = footLines > 0 ? 0.22 + footLines * 0.26 : 0;
  const planH      = Math.max(BODY_H - (y - BODY_Y) - (trialsH > 0 ? trialsH + 0.26 : 0), 0.5);

  if (planItems.length > 0) {
    slide.addText(mkBullets(planItems, { size: 14, gap: 7 }), {
      x: MARGIN, y, w: W - MARGIN * 2, h: planH,
      fontFace: FONT, valign: "top",
    });
  }

  // ── Evidence footnote: trials (NCT) + PubMed references ─────────────────
  if (trialItems.length > 0 || refItems.length > 0) {
    const footY = H - FTR_H - trialsH - 0.04;
    hRule(prs, slide, footY - 0.10, RULE);

    if (trialItems.length > 0 && refItems.length > 0) {
      // Two-column: NCT left, PMID right
      const colW = (W - MARGIN * 2 - 0.30) / 2;

      slide.addText("Trials to consider:", {
        x: MARGIN, y: footY - 0.02, w: colW, h: 0.20,
        fontFace: FONT, fontSize: 9.5, bold: false, color: SUBTLE, margin: 0,
      });
      slide.addText(trialItems.slice(0, 3).join("\n"), {
        x: MARGIN, y: footY + 0.20, w: colW, h: trialsH - 0.22,
        fontFace: FONT, fontSize: 10, color: TEAL_DIM,
        margin: 0, valign: "top",
      });

      vRule(prs, slide, MARGIN + colW + 0.13, footY - 0.02, trialsH + 0.04);

      slide.addText("Key references:", {
        x: MARGIN + colW + 0.28, y: footY - 0.02, w: colW, h: 0.20,
        fontFace: FONT, fontSize: 9.5, bold: false, color: SUBTLE, margin: 0,
      });
      slide.addText(refItems.join("\n"), {
        x: MARGIN + colW + 0.28, y: footY + 0.20, w: colW, h: trialsH - 0.22,
        fontFace: FONT, fontSize: 10, color: MUTED,
        margin: 0, valign: "top",
      });

    } else if (trialItems.length > 0) {
      slide.addText("Trials to consider  (AI-identified):", {
        x: MARGIN, y: footY - 0.02, w: W - MARGIN * 2, h: 0.20,
        fontFace: FONT, fontSize: 9.5, color: SUBTLE, margin: 0,
      });
      slide.addText(trialItems.slice(0, 3).join("   ·   "), {
        x: MARGIN, y: footY + 0.20, w: W - MARGIN * 2, h: trialsH - 0.22,
        fontFace: FONT, fontSize: 10.5, color: TEAL_DIM,
        margin: 0, valign: "top",
      });

    } else {
      slide.addText("Key references:", {
        x: MARGIN, y: footY - 0.02, w: W - MARGIN * 2, h: 0.20,
        fontFace: FONT, fontSize: 9.5, color: SUBTLE, margin: 0,
      });
      slide.addText(refItems.join("   ·   "), {
        x: MARGIN, y: footY + 0.20, w: W - MARGIN * 2, h: trialsH - 0.22,
        fontFace: FONT, fontSize: 10.5, color: MUTED,
        margin: 0, valign: "top",
      });
    }
  }
}

// ── Marker data parser ────────────────────────────────────────────────────────

function parseMarkers(raw) {
  if (!raw || !Array.isArray(raw) || raw.length < 2) return null;
  const labels = [], values = [];
  for (const e of raw) {
    const d = e.date || e.OrderDate || e.ResultDate || "";
    const v = e.value || e.ResultValue || e.result_value || "";
    if (d && v !== "") {
      const n = parseFloat(String(v).replace(",", ""));
      if (!isNaN(n)) { labels.push(d); values.push(n); }
    }
  }
  return labels.length >= 2 ? { labels, values } : null;
}

// ── Main ───────────────────────────────────────────────────────────────────────

function main() {
  let raw = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", c => { raw += c; });
  process.stdin.on("end", () => {
    let input;
    try { input = JSON.parse(raw); }
    catch (e) {
      process.stderr.write(`tumor_board_slides.js: invalid JSON: ${e.message}\n`);
      process.exit(1);
    }

    const sc         = input.slides       || {};
    const markersRaw = input.tumor_markers_raw || null;
    const outputPath = input.output_path  || "tumor_board_slides.pptx";

    const prs = new pptxgen();
    prs.layout = "LAYOUT_WIDE";
    prs.author = "Rush AI Tumor Board";
    prs.title  = `GYN Tumor Board — ${sc.patient_title || "Case"}`;

    buildSlide1(prs, sc);
    buildSlide2(prs, sc);
    buildSlide3(prs, sc, markersRaw);
    buildSlide4(prs, sc);
    buildSlide5(prs, sc);

    prs.writeFile({ fileName: outputPath })
      .then(() => { process.stdout.write(outputPath + "\n"); process.exit(0); })
      .catch(err => {
        process.stderr.write(`tumor_board_slides.js: write failed: ${err.message}\n`);
        process.exit(1);
      });
  });
}

main();
