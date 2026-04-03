---
status: complete
priority: p2
issue_id: "123"
tags: [code-review, architecture, performance, reliability]
dependencies: []
---

# 123 — Selection and termination strategies share the clinical deployment and quota

## Problem Statement

`KernelFunctionSelectionStrategy` and `KernelFunctionTerminationStrategy` in `group_chat.py:207-333` each create their own kernel using `AZURE_OPENAI_DEPLOYMENT_NAME` — the same deployment used by the 10 clinical agents. The selection LLM runs on every agent turn with a full conversation history dump (`allow_dangerously_set_content=True`), consuming thousands of tokens per call. Under moderate load, selection and termination calls compete with clinical inference for rate-limit quota. A quota exhaustion or throttle on the shared deployment blocks both routing logic and clinical responses simultaneously.

## Findings

- `group_chat.py:207-333` — `KernelFunctionSelectionStrategy` and `KernelFunctionTerminationStrategy` instantiation; both read `AZURE_OPENAI_DEPLOYMENT_NAME` directly

## Proposed Solution

1. Add an optional environment variable `AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME` that defaults to `AZURE_OPENAI_DEPLOYMENT_NAME` when not set.
2. Configure the selection and termination kernels to use this variable instead of the clinical deployment variable.
3. In production, set `AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME` to a smaller, cheaper model (e.g., GPT-4o-mini) that has its own rate-limit quota separate from the clinical GPT-4o deployment.
4. Document the new env var in `.env.example` and deployment documentation.

## Acceptance Criteria

- [ ] `KernelFunctionSelectionStrategy` uses `AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME` (falls back to clinical deployment when not set)
- [ ] `KernelFunctionTerminationStrategy` uses the same configurable selection deployment
- [ ] `AZURE_OPENAI_SELECTION_DEPLOYMENT_NAME` is documented in `.env.example` with a description
- [ ] Clinical agent quota is not consumed by routing calls when a separate selection deployment is configured
