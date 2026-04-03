---
status: pending
priority: p3
issue_id: "162"
tags: [code-review, performance]
dependencies: []
---

# Shared aiohttp.ClientSession in ClinicalTrialsPlugin

## Problem Statement

`clinical_trials.py` creates a new `aiohttp.ClientSession` per API call (lines 306, 384). If `display_more_information_about_a_trial` is called 3-5 times for promising trials, this means 3-5 separate TCP+TLS handshakes to clinicaltrials.gov.

## Proposed Solutions

Create shared session at `__init__` time with async cleanup. Expected savings: ~100-200ms per subsequent call.

## Work Log
- 2026-04-02: Identified during code review (performance-oracle)
