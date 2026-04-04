---
status: pending
priority: p2
issue_id: "158"
tags: [code-review, security, hipaa, auth]
dependencies: []
---

# Demo Routes Lack Per-Request Authentication (Defense-in-Depth)

## Problem Statement

Demo view routes (`/view/`) are gated by `DEMO_ROUTES_ENABLED` env var (default false — good). However, the route handlers themselves contain zero authentication checks. If enabled in staging/demo, any unauthenticated HTTP client can retrieve full clinical notes by guessing `conversation_id` and `patient_id`.

## Findings

- **Source**: Security Sentinel
- **Evidence**: `src/routes/views/patient_data_answer_routes.py`, `src/routes/views/patient_timeline_routes.py`
- **Related**: todos/100-complete-p1-unauthenticated-view-phi-routes.md (marked complete but 3/5 acceptance criteria unfulfilled)

## Proposed Solutions

### Option A: Add X-MS-CLIENT-PRINCIPAL-ID header check inside handlers (Recommended)
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria
- [ ] View route handlers validate authentication header
- [ ] Unauthenticated requests return 401 even when DEMO_ROUTES_ENABLED=true

## Work Log
- 2026-04-02: Identified during code review (security-sentinel)
