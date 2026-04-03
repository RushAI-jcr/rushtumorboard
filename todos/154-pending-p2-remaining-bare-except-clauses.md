---
status: pending
priority: p2
issue_id: "154"
tags: [code-review, security, quality]
dependencies: []
---

# Remaining Bare except: Clauses

## Problem Statement

Two bare `except:` clauses remain after the null-safety pass converted others to `except Exception:`:
1. `chats.py:198` — catches all exceptions during WebSocket error reporting
2. `chat_context_accessor.py:55` — silently swallows ANY exception reading chat context blob, returning fresh ChatContext. This masks authorization failures, corruption, and `SystemExit`.

## Findings

- **Source**: Security Sentinel
- **Evidence**: `src/routes/api/chats.py` line 198, `src/data_models/chat_context_accessor.py` line 55

## Proposed Solutions

### Option A: Convert to except Exception with logging (Recommended)
- **Effort**: Small (2 lines each)
- **Risk**: None

## Acceptance Criteria
- [ ] No bare `except:` clauses remain in codebase
- [ ] `chat_context_accessor.py` logs the exception at WARNING level

## Work Log
- 2026-04-02: Identified during code review (security-sentinel)
