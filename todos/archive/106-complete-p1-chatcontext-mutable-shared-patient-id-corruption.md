---
status: complete
priority: p1
issue_id: "106"
tags: [code-review, architecture, security, phi, patient-safety]
dependencies: []
---

# 106 — Mutable `ChatContext` Shared by Reference Enables Silent Patient ID Corruption

## Problem Statement

`ChatContext` (`src/data_models/chat_context.py`) is a plain mutable Python object. `patient_id`, `patient_data`, and `output_data` are instance attributes written directly by plugin methods. `PatientDataPlugin.load_patient_data()` writes `self.chat_ctx.patient_id = patient_id` (line 87 of `patient_data.py`) with no lock, no set-once guard, and no validation that the ID being written matches any previously set value.

`group_chat.py:110-115` passes the same `chat_ctx` reference to multiple agents. If two agents are invoked concurrently — as happens during `asyncio.gather` inside any tool — or if two HTTP requests share the same `chat_ctx` instance via a caching race in `ChatContextAccessor`, these writes are unserialized. The result is silent patient ID substitution: an agent can begin processing patient A's data and silently switch to patient B's data partway through if a concurrent request writes a different `patient_id` to the shared object. This is the highest clinical safety risk in the codebase. A tumor board summary generated under these conditions could contain the wrong patient's data with no indication of the error.

## Findings

- `src/data_models/chat_context.py:1-21` — no locking, no set-once enforcement, attributes are freely reassignable.
- `src/scenarios/default/group_chat.py:110-115` — `chat_ctx` passed by reference to all agents in the group chat; all agents share the same mutable object.
- `src/scenarios/default/tools/patient_data.py:87` — `self.chat_ctx.patient_id = patient_id` direct write without checking current value.
- `ChatContextAccessor` (accessor layer) — if it implements any caching keyed on `chat_id`, two concurrent requests with the same `chat_id` may receive the same `chat_ctx` reference, allowing cross-request contamination.

## Proposed Solution

**Option A — Set-once enforcement (minimal change, high safety):**

```python
class ChatContext:
    _patient_id: str | None = None

    @property
    def patient_id(self) -> str | None:
        return self._patient_id

    @patient_id.setter
    def patient_id(self, value: str) -> None:
        if self._patient_id is not None and self._patient_id != value:
            raise ValueError(
                f"ChatContext: patient_id already set to {self._patient_id!r}; "
                f"refusing to overwrite with {value!r}"
            )
        self._patient_id = value
```

This turns silent corruption into a loud, immediate exception that surfaces in logs and can be caught and alerted on.

**Option B — Per-plugin context snapshots (architectural improvement):**

At plugin construction time, give each plugin a frozen snapshot of the context fields it needs rather than a live mutable reference. Plugins read from the snapshot and write results to a separate output accumulator.

**Option C — `asyncio.Lock` on writes (minimum concurrency fix):**

Add an `asyncio.Lock` to `ChatContext` and require all attribute writes to be performed under `async with ctx.write_lock:`. This prevents concurrent writes but still allows sequential overwriting, so Option A or B should accompany this.

**Recommended:** Implement Option A immediately (low risk, high impact). Pair with a review of `ChatContextAccessor` caching to ensure different requests never share the same instance.

## Acceptance Criteria

- [ ] `patient_id` on `ChatContext` cannot be silently overwritten to a different value mid-session; attempting to do so raises `ValueError`
- [ ] `ChatContextAccessor` does not return the same `ChatContext` instance to two concurrent requests for different patients
- [ ] A clinical safety test verifies that concurrent `load_patient_data` calls for two different patients raise an error or operate on separate `ChatContext` objects (no cross-contamination)
- [ ] All existing tests continue to pass (set-once guard must not break legitimate single-patient flows)
