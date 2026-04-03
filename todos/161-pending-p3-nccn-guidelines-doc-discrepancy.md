---
status: pending
priority: p3
issue_id: "161"
tags: [code-review, docs, accuracy]
dependencies: []
---

# ClinicalGuidelines Documentation Discrepancy

## Problem Statement

`docs/scenarios.md` and `README.md` say ClinicalGuidelines covers "endometrial, cervical, ovarian, vaginal, vulvar" but `agents.yaml` instructions state ovarian and cervical are "training knowledge only" — only uterine, vaginal, and vulvar have loaded NCCN PDFs.

## Proposed Solutions

Clarify in docs that only 3 cancer types have PDF-backed retrieval; ovarian and cervical use model training knowledge.

## Work Log
- 2026-04-02: Identified during code review (architecture-strategist)
