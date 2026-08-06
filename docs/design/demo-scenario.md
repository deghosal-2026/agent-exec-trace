# Demo Agent Scenario — v0.1.0

> Reality anchor for the whole product. One LangGraph agent with three behavioral
> paths: **normal**, **loop**, and **high-cost**. Later SDK, analytics, and UI work
> must reference this scenario as the source of truth.

## Agent: `request-triage`

`request-triage` is a deterministic support-triage agent. Given an inbound service
request, it decides whether to **resolve** it from the knowledge base, or **escalate**
it to a human operator.

It exercises two tools:

- `search_kb(query)` — looks up an answer in a knowledge base. Deterministic: returns
  a fixed hit for known queries, otherwise `None`.
- `lookup_account(account_id)` — loads account context. Deterministic: fails for a
  set of "missing" account IDs.

The agent is seeded entirely by its input, so behavior is reproducible: the same input
file produces the same category of run every time.

## What a normal run looks like

Input: a well-scoped request with a known answer and a valid account.

1. Agent plans: identify intent, pick `search_kb`.
2. Calls `search_kb` once → returns a hit.
3. Calls `lookup_account` once → valid.
4. Resolves the request.

Trace shape: one root `invoke_agent` span with a small number of child spans
(`plan`, two `execute_tool`) and one `ok` outcome. Low cost, no anomalies.
A normal run is the baseline cohort for version compare.

## What a "bad run" (loop) looks like

Input: a request whose `account_id` is missing.

1. Agent plans to resolve the request.
2. Calls `lookup_account` → expected failure (account missing).
3. Re-compiles a query, calls `search_kb` → `None`.
4. Re-runs `plan` → same plan, calls `lookup_account` again → fails.
5. Cycles the same "search then retry account" sequence repeatedly without converging.

Trace shape: a run with repeated identical tool sequences (`search_kb` and
`lookup_account` firing many times across turns). This is what the **loop detector**
must flag with evidence pointing at the repeated `search_kb` calls.

## What a run "bad run" (high-cost) looks like

Input: a broad, open-ended request.

1. The agent repeatedly re-plans and issues many `search_kb` queries across many turns.
2. Each turn is treated as a billed model turn, accumulating estimated cost per call.
3. No early exit; cost rises well above the per-run baseline.

Trace shape: a run with an unusually high number of tool turns and cumulative estimated
cost several multiples of a normal run. This is what the **cost detector** must flag,
with a stored explanation of amount and why it was considered unusual.

## Why agent vs "framework" scenario

The agent is built directly on LangGraph but keeps its behavior in plain Python tools.
Because behavior is driven by inputs, the same agent run can be replayed on demand — the
basis for the demo seed/replay workflow and analytics reprocessing tests.

## Related docs

- Scenario matrix and fixtures: planned under WBS 1.3 / 1.4.
  `examples/demo-agent/fixtures/` and `examples/demo-agent/scenario-matrix.md`.
- Detector validation matrix: WBS 6.7.