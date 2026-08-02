# agent-exec-trace — PRD

**Execution traces for agent behavior. OpenTelemetry-conformant, local-first, framework-agnostic.**

| Field | |
|---|---|
| Status | Draft |
| Version | v0.1.0 |
| Created | 2026-08-02 |
| Author | Debashish Ghosal |

---

## 1. WHY — The Problem

### 1.1 The Gap

A normal service trace shows latency, errors, and dependency calls. It tells you *what services did*. It cannot tell you why an agent made a bad decision, changed plans three times, got stuck between two tools, or quietly drifted into expensive low-value behavior.

Yet these are precisely the behaviors that determine whether an agent is useful or dangerous. As agents become long-running, stateful, and tool-using, the gap between "the API returned 200" and "the agent behaved correctly" is where teams lose trust, waste budget, and ship broken agent systems.

**The painful truth:** Most teams can tell you if a service is up. They cannot tell you what an agent *thought* it was doing.

### 1.2 Who Feels This

| Persona | When they hit the wall |
|---|---|
| **Agent Developer** | An agent run failed or burned $2 in tokens. They stare at raw logs and guess where it went wrong. |
| **LLMOps Engineer** | They shipped a new prompt version. Token costs are up. Is the new version actually better? They can't prove it. |
| **Platform Engineer** | 12 teams are running agents across the org. No one knows which agents are looping, which tool patterns correlate with failure, or what the fleet-level cost-per-success looks like. |
| **Engineering Manager** | An agent system went to production. When something breaks, the team's time-to-diagnose is measured in hours, not minutes. |

### 1.3 Why Existing Tools Don't Solve It

| Tool | What it does | What it misses |
|---|---|---|
| **OpenLLMetry** (Traceloop, 7.3k stars) | OTel traces for LLM *calls* — tokens, latency, model params | No agent behavior semantics. It traces the LLM API call, not the agent's decision path. |
| **Langfuse** (32.4k stars) | Full LLM engineering platform — evals, prompt mgmt, datasets, playground | Broad platform, not focused on agent runtime diagnostics. LangChain/LlamaIndex callback-based, not OTel-native. |
| **Generic OTel** (Prometheus, Grafana, Tempo) | Service traces and metrics | No agent-specific span types. A tool call looks like any other RPC. Loop detection, cost-per-run, and version diff don't exist. |

### 1.4 The OTel GenAI Opportunity

**OpenTelemetry now has official semantic conventions for GenAI agents** (in Development status as of 2026). They define span types for `invoke_agent`, `plan`, `execute_tool`, `retrieval`, `create_memory`, `search_memory`, and more.

But a specification without a reference implementation is just a document. No open-source tool today:

- Fully conforms to OTel GenAI agent conventions
- Ships an instrumentation SDK that wraps LangGraph and raw Python agents
- Adds behavior analytics on top (loop detection, cost anomaly, drift)
- Provides a run explorer UI purpose-built for agent behavior traces

`agent-exec-trace` fills that gap. It is the reference implementation that makes OTel GenAI agent conventions actionable.

---

## 2. WHAT — Product Scope

### 2.1 v0.1.0 Feature Set

| # | Feature | Description |
|---|---|---|
| F1 | Behavior trace schema | Span/event types conforming to OTel Gen AI agent semconv: `invoke_agent`, `plan`, `execute_tool`, `retrieval`, `memory` operations. Extended with custom attributes for loops, cost, version metadata. |
| F2 | Instrumentation SDK | Python package wrapping LangGraph agents and raw Python agents (`@trace_agent` decorator). Auto-instruments agent lifecycle events into OTel spans. |
| F3 | OTLP export | All traces exported via OpenTelemetry Collector to Tempo/Jaeger. Compatible with any OTLP backend (Grafana, Datadog, Honeycomb). |
| F4 | Run explorer UI | Single-run timeline view showing plan→tool→memory→cost events in a waterfall. Clickable spans with detail panels. Search and filter across runs. |
| F5 | Fleet behavior dashboard | Cross-agent views: tool mix, cost-per-success, intervention rate. Groupable by agent, team, workload type. |
| F6 | Anomaly detection engine | Loop detection (tool called > N times in sequence), cost surge detection (run cost exceeds baseline), retry storm detection. |

### 2.2 Deferred to v0.2+

| # | Feature | v0.2+ |
|---|---|---|
| F7 | Version comparison | Side-by-side trace diff between agent versions. Structured behavior change report (tool usage delta, cost delta, success delta). |
| F8 | Search & filter across runs | "Show all runs where tool X was called > 5 times." "All runs that escalated to human." |
| F9 | Decision trace | "Why did the agent pick tool A over tool B at step 4?" Context-window visibility. |
| F10 | Cost attribution | Per-agent, per-workload, per-user cost breakdown over time. Budget tracking. |
| F11 | Memory audit trail | What was written, retrieved, overwritten. Stale data detection. |
| F12 | Human intervention review | Operator escalations: when, why, what happened after. |
| F13 | Deeplink/share | Permalink any trace view. Share with team. |
| - | PydanticAI adapter | Third framework adapter. Validates the schema is truly framework-agnostic. |
| - | Policy overlay integration | Correlate trace events with policy/approval events from external governance systems. |

### 2.3 v0.2.0 Backlog (Ship Plan)

| # | Feature | Priority | Journeys | Description |
|---|---|---|---|---|
| F7 | Version comparison | P0 | J2 | Side-by-side trace diff. Behavior change report (tool usage delta, cost delta, success delta). Prompt/model correlation views. |
| F8 | Search & filter across runs | P0 | J5 | Full-text search on traces: tool name, error type, cost range, date range. Saved search templates. |
| F9 | Decision trace | P1 | J6 | "Why did the agent pick tool A over tool B?" Context-window visibility. Model reasoning output at decision points. |
| F10 | Cost attribution dashboard | P1 | J7 | Per-agent, per-workload, per-user cost breakdown. Budget tracking. Cost-vs-success curves. |
| F11 | Memory audit trail | P1 | J8 | Memory CRUD timeline per agent. Stale data detection (reads vs. writes with version skew). Overwrite conflict surface. |
| F12 | Human intervention review | P2 | J9 | Approval/escalation timeline. Intervention rate by agent. "Why was a human needed?" root cause panel. |
| F13 | Deeplink/share | P2 | J10 | Permalink any trace view + specific span. Share via URL. No screenshots needed. |
| - | PydanticAI adapter | P2 | - | Third runtime adapter. Proves schema is truly framework-agnostic. |
| - | Policy overlay integration | P2 | - | Correlate trace events with policy/approval events from external governance systems (OPA, custom). |
| - | Multi-agent interaction maps | P3 | - | When agent A calls agent B, show the parent-child relationship in a topology view. |
| - | Public demo workload pack | P3 | - | Seeded bad runs (loops, cost spikes, drift) as a downloadable demo. "Run this and see what agent-exec-trace catches." |
| - | Benchmark-driven diagnostics | P3 | - | Standard benchmark agents instrumented. Publish diagnostics from real runs. |

### 2.4 Non-Goals (Will Not Build)

| Not building | Why |
|---|---|
| Full trace backend | Uses existing backends (Tempo, Jaeger). Not a replacement for them. |
| Evaluation framework | Shows *what happened*, not *whether it was correct*. Complements eval tools like EvalForge. |
| Prompt management or datasets | Langfuse territory. Stay focused on runtime observability. |
| SaaS/cloud-hosted version | Local-first OSS. Self-hosted only. |
| Policy enforcement engine | Observability, not governance. Integrates with policy tools but does not enforce. |

### 2.5 Architecture

```
┌─────────────────────────────────────────────┐
│           Agent Runtime                      │
│  ┌──────────────┐  ┌─────────────────────┐  │
│  │  LangGraph    │  │  Raw Python Agent   │  │
│  │  (auto-wrap)  │  │  (@trace_agent)     │  │
│  └──────┬───────┘  └──────────┬──────────┘  │
│         │                     │              │
│         ▼                     ▼              │
│  ┌──────────────────────────────────────┐    │
│  │    Instrumentation SDK (Python)       │    │
│  │    • OTel span/event creation         │    │
│  │    • OTel GenAI semconv compliance    │    │
│  │    • Custom attrs: loops, cost, ver   │    │
│  └──────────────────┬───────────────────┘    │
└─────────────────────┼────────────────────────┘
                      │ OTLP
                      ▼
              ┌───────────────┐
              │  OTel Collector │
              └───────┬───────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌──────────┐
   │  Tempo  │  │  Jaeger  │  │ Prometheus│
   │ (traces)│  │ (traces) │  │ (metrics) │
   └────┬────┘  └────┬─────┘  └─────┬─────┘
        │            │              │
        └────────────┼──────────────┘
                     ▼
         ┌────────────────────────┐
         │  Behavior Analytics     │
         │  • loop detection       │
         │  • cost anomaly         │
         │  • drift signals        │
         └───────────┬────────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │  Run Explorer UI        │
         │  (FastAPI + React)      │
         │  • timeline view        │
         │  • fleet dashboard      │
         │  • trace search/filter  │
         └────────────────────────┘
```

### 2.6 Stack

| Layer | Tech | Why |
|---|---|---|
| Instrumentation | OpenTelemetry Python SDK | Industry standard. Vendor-neutral. |
| Collection | OpenTelemetry Collector | Standard OTLP pipeline. |
| Traces | Tempo (primary), Jaeger (fallback) | OSS. Local-first. |
| Metrics | Prometheus | Standard metric store. |
| Dashboards | Grafana (optional overlay) | Standard dashboard tool. |
| API | FastAPI | Python, async, well-typed. |
| UI | React + Tailwind | Clean, responsive. |
| Analytics | Python (pandas/numpy) | Compute loops, anomalies, drifts. |
| Sample workloads | LangGraph agents + raw Python agents | Real agents, seeded bad runs. |

---

## 3. CUSTOMER JOURNEY — Full Vision (10 Journeys)

> v0.1.0 ships journeys 1, 4, 2, 3 in that build order. Journeys 5–10 are v0.2+.

### Journey 1: Debug a Single Bad Run *(v0.1.0)*

**Scenario:** An operator notices a production agent run that took 3x the normal time and cost. They have the run ID. They want to understand what happened.

1. Opens the run explorer, enters the run ID.
2. Waterfall timeline shows the full execution trace: `invoke_agent` → `plan` → `execute_tool(get_weather)` → `execute_tool(get_weather)` → `execute_tool(get_weather)` → ...
3. Loop detection badge highlights the tool-call loop in red.
4. Hovers over each span to see: tool name, arguments, duration, tokens consumed, cost.
5. Clicks the first loop iteration to see the decision context — why did it call again?
6. Cost bar at the top shows $1.82 burned on this run vs. $0.34 baseline.
7. Shares the trace link in Slack. "This is the loop."

**Success:** Time-to-diagnose drops from hours of log-grepping to minutes of visual inspection.

---

### Journey 4: Scan the Fleet for Drift *(v0.1.0)*

**Scenario:** An LLMOps lead manages 6 agents across 3 teams. A new model version was rolled out last week. They want to know if anything changed.

1. Opens fleet dashboard. Selects "Last 7 days."
2. Top row: cards showing total runs, success rate, avg cost-per-run, anomaly count.
3. **Drift panel:** Agent "oncall-triage" shows a 22% increase in `execute_tool` calls per run since the model update.
4. **Cost panel:** Agent "code-review" cost-per-success went from $0.08 to $0.14.
5. **Tool mix panel:** Agent "incident-commander" started using `search_runbooks` 40% less after a prompt change.
6. Clicks into "oncall-triage" to see individual runs from the drift period.

**Success:** Fleet-level awareness without manually querying each agent. Drift is caught before it becomes a production incident.

---

### Journey 2: Compare Two Agent Versions *(v0.1.0)*

**Scenario:** A team changed the system prompt and switched from `gpt-4o-mini` to `claude-3.5-sonnet`. They want to know if v2 is actually better.

1. Opens version comparison. Selects v1 and v2, time range: last 48 hours each.
2. **Tool usage delta:** `get_weather` called 12% more in v2. `search_docs` called 18% less.
3. **Cost delta:** v2 avg cost-per-run: $0.52 vs v1 $0.38. But avg tokens-per-success dropped.
4. **Retry delta:** v2 retry rate: 4% vs v1: 11%. Improvement.
5. **Success delta:** v2 success rate: 89% vs v1: 81%. Improvement despite higher cost.
6. Drills into the highest-cost v2 run to understand what's different.
7. Decides: v2 is better. Higher cost is acceptable because success rate improved.

**Success:** Version upgrade decisions backed by structured behavior data, not gut feel.

---

### Journey 3: Auto-Detect Loops and Cost Spikes *(v0.1.0)*

**Scenario:** Over the weekend, 3 agent runs went into a retry spiral. No one noticed until Monday's bill.

1. Anomaly engine runs continuously on incoming traces.
2. Detects: agent "release-notes" called `git_diff` 47 times in a single run (baseline: 2-3).
3. Detects: agent "code-review" single run cost hit $4.12 (baseline: $0.15).
4. Alerts fire to a configurable channel (Slack webhook, log, Prometheus alert).
5. Monday morning: team opens the alert, clicks through to the flagged trace.
6. Root cause identified in minutes — the release-notes agent was hallucinating file paths and retrying.

**Success:** Anomalous behavior is caught automatically, not discovered on the billing page.

---

### Journey 5: Search & Filter Across Runs *(v0.2)*

**Scenario:** A developer remembers a specific tool call went wrong last week but doesn't have the run ID.

1. Opens search. Types: `execute_tool: git_push AND error AND cost > 1.0`.
2. Returns 3 matching runs from the last 30 days.
3. Sorted by cost descending. Opens the most expensive one.
4. Finds the exact failure: `git_push` failed with permission error, agent retried 4 times.

---

### Journey 6: Trace a Specific Decision *(v0.2)*

**Scenario:** An agent chose tool A over tool B. The developer wants to know why.

1. Opens the run at the decision point (step 4 of 8).
2. Decision trace panel shows: the model's reasoning output at that step, the tool definitions available, the conversation context leading up to the choice.
3. Developer sees that tool B was excluded because the model hallucinated a required parameter.
4. Fixes the tool description to make the parameter optional.

---

### Journey 7: Cost Attribution *(v0.2)*

**Scenario:** The engineering manager asks: "Which team is spending the most on agent runs?"

1. Opens cost dashboard. Groups by team.
2. Team A: $412 this month (code-review agent, 3,200 runs).
3. Team B: $87 this month (oncall-triage agent, 180 runs).
4. Drills into Team A: 72% of cost is from a single high-token model. Recommends switching to a cheaper model for non-critical reviews.

---

### Journey 8: Memory Audit Trail *(v0.2)*

**Scenario:** An agent is making decisions based on stale data written to memory.

1. Opens memory audit view for a specific agent.
2. Timeline shows: `create_memory(user_preference, v1)` → `search_memory(user_preference)` → `update_memory(user_preference, v3)`.
3. Developer sees that the agent read v1 and wrote v3, but a human overrode v2 in between. The agent overwrote the human edit.
4. Adds a `read-before-write` check to the agent's memory policy.

---

### Journey 9: Human Intervention Review *(v0.2)*

**Scenario:** The team wants to reduce human escalations — each approval is a bottleneck.

1. Opens intervention dashboard. Filters by agent: "deployment-approval."
2. 43 approvals this month. Avg approval wait time: 14 minutes.
3. Most common approval reason: "Cost exceeds threshold." Second: "Tool write to production."
4. Team decides to raise the cost threshold for non-destructive tools and auto-approve staging writes.
5. Follows up in 2 weeks: approvals dropped 62%.

---

### Journey 10: Deeplink / Share a Trace *(v0.2)*

**Scenario:** A developer finds a critical bug in a trace and needs the whole team to see it.

1. Clicks "Copy link" on the trace view.
2. Pastes into Slack: `https://agent-exec-trace.local/traces/run_abc123?span=step_4`
3. Teammates click and land directly on the problematic span, fully zoomed, with the annotation "Loop starts here."
4. No screenshots. No "scroll to step 4." One link.

---

## 4. RESEARCH — Competitive Landscape & OTel Standards Analysis

### 4.1 OpenTelemetry GenAI Agent Conventions — What Exists

The OTel semantic conventions for GenAI agents (repo: `open-telemetry/semantic-conventions-genai`, status: **Development**) define:

| Convention | Span Type | Key Attributes |
|---|---|---|
| `invoke_agent` (INTERNAL) | Local agent run within same process | `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.agent.version`, `gen_ai.agent.description` |
| `invoke_agent` (CLIENT) | Agent run via remote service | Same as above + `gen_ai.provider.name`, `server.address` |
| `plan` | Agent planning/task decomposition phase | Attaches as child of `invoke_agent` |
| `execute_tool` | Tool execution | Tool name, arguments, result |
| `retrieval` | RAG/vector search retrieval | `gen_ai.data_source.id` |
| `create_memory` / `search_memory` / `update_memory` / `delete_memory` | Memory CRUD operations | Memory store identifier |
| `invoke_workflow` | Multi-agent workflow orchestration | Parent span for sub-agent invocations |

These are exactly the building blocks needed. `agent-exec-trace` will implement instrumentation that emits spans conforming to these conventions.

### 4.2 Competitive Gap Analysis

| Tool | OTel Conformant | Agent Behavior Spans | In-Process Instrumentation | Loop Detection | Cost Per Run | Version Diff | Open Source | Local-First |
|---|---|---|---|---|---|---|---|---|
| **agent-exec-trace** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenLLMetry (Traceloop) | ✅ | ❌ LLM calls only | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Langfuse | ❌ Callback-based | ⚠️ Limited | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ |
| LangSmith | ❌ Proprietary | ⚠️ LangChain-only | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Arize Phoenix | ❌ Proprietary | ❌ LLM calls | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ |

### 4.3 Gaps We Fill (Potential OTel Contribution)

The OTel GenAI agent conventions are **in Development.** Several concepts are missing that `agent-exec-trace` could propose back:

| Concept | Current OTel Coverage | Proposed Extension |
|---|---|---|
| **Loop/retry semantics** | Not defined | `gen_ai.agent.loop.count` — number of times a tool was called in sequence within a run. `gen_ai.agent.loop.detected` — boolean flag from detection engine. |
| **Cost attribution** | Token usage only (`gen_ai.usage.input_tokens`) | `gen_ai.agent.cost.estimated` — estimated USD cost of the operation. `gen_ai.agent.run.cost.total` — total cost of a single agent run. |
| **Version comparison** | `gen_ai.agent.version` exists as an attribute | No comparison semantics. Could propose a `gen_ai.agent.version.diff` event type for structured version-to-version behavior deltas. |
| **Budget/burn rate** | Not defined | `gen_ai.agent.budget.limit` and `gen_ai.agent.budget.consumed` for budget-aware agent runs. |
| **Memory mutation events** | CRUD operations defined but no mutation tracking | `gen_ai.memory.key` — the key being mutated. `gen_ai.memory.previous_value_hash` — for detecting overwrites. |
| **Human intervention** | Not defined | `gen_ai.agent.human_approval` span type. `gen_ai.agent.approval.reason` — why the human was asked. `gen_ai.agent.approval.decision` — approve/deny/escalate. |
| **Drift signal** | Not defined | `gen_ai.agent.drift.score` — statistical distance from baseline behavior distribution. |

### 4.4 Conformance Strategy

1. **v0.1.0** — Instrumentation SDK emits fully conformant OTel GenAI agent spans. All attributes use `gen_ai.*` namespace.
2. **v0.1.0** — Custom attributes (`gen_ai.agent.loop.count`, `gen_ai.agent.cost.estimated`, etc.) are prefixed and documented as extensions pending OTel adoption.
3. **Post-v0.1.0** — Open an issue/PR against `open-telemetry/semantic-conventions-genai` proposing the extensions above as formal semconv additions.
4. **Goal** — Become the reference implementation. When someone asks "how do I instrument agents with OTel GenAI conventions?", the answer is `agent-exec-trace`.

---

## Appendix: Build Order

| Milestone | Scope |
|---|---|
| **M1 — Schema + Instrumentation** | Trace schema, LangGraph wrapper, `@trace_agent` decorator, OTLP export |
| **M2 — Run Explorer** | Timeline UI, span detail, cost overlay, search |
| **M3 — Analytics** | Loop detection, cost anomaly, retry detection |
| **M4 — Fleet Dashboard** | Cross-agent views, drift panel, tool mix, cost-per-success |
| **M5 — Anomaly Alerts** | Configurable alert rules, webhook/API output |
| **M6 — Hardening** | Tests, docs, OpenSSF badge, PyPI publish, launch article |

M1 is the critical path. Everything else builds on the schema quality.
