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

### 1.5 Why Standardized Views Matter

Observability products mature when they stop being "a pile of traces" and become a shared operational language. The same thing happened in service observability: waterfall traces, RED views, service maps, and drill-down workflows became standard because teams needed common views they could teach, document, and automate around.

Agent observability needs the same standardization layer. Without shared views, every team builds its own dashboards, every investigation starts from scratch, and every incident review becomes a one-off interpretation exercise.

`agent-exec-trace` should define a small set of **standardized operator views** that work across frameworks and backends:

- **Run Timeline**: the canonical answer to "what happened in this run?"
- **Fleet Health**: the canonical answer to "which agents need attention right now?"
- **Version Compare**: the canonical answer to "did this change improve or degrade behavior?"
- **Anomaly Inbox**: the canonical answer to "what needs investigation first?"
- **Cost Attribution**: the canonical answer to "where is budget going and is it buying reliability?"

These views are product features, not just UI screens. They create shared vocabulary for developers, operators, and managers, and they make interop possible with systems like Grafana, Tempo, Jaeger, Prometheus, CI pipelines, alert managers, and governance tooling.

### 1.6 Product Maturity Thesis

The product should evolve in three recognizable stages:

| Stage | What users get | Product risk |
|---|---|---|
| **Developing** | Trace capture + single-run debugging | Product is useful but reactive. Operators still have to know what to look for. |
| **Maturing** | Fleet views, comparison, anomaly surfacing, cost visibility | Product becomes operationally useful. Teams can manage a portfolio of agents, not just debug one run. |
| **Mature** | Standardized views, workflow integration, interop, governance overlays, reference conventions | Product becomes part of the operating model. It is where teams triage, compare, route, and explain agent behavior. |

This PRD intentionally focuses on moving from **developing** to **maturing** without pretending to be a full AI platform. The product becomes mature by being the best at runtime behavior observability and by integrating cleanly with the broader observability and governance ecosystem.

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

### 2.1.1 v0.1.0 Standardized Operator Views

v0.1.0 should not just ship raw features. It should ship **opinionated default views** that turn OTel traces into repeatable operator workflows.

| View | Primary user | Core question answered | Required inputs |
|---|---|---|---|
| **Run Timeline** | Agent developer, on-call engineer | What happened in this run, in order? | `invoke_agent`, `plan`, `execute_tool`, retrieval, memory, cost, error spans |
| **Run Summary Panel** | Agent developer | Why was this run expensive / slow / wrong? | Aggregated cost, tool count, retries, loop flags, intervention events |
| **Fleet Health Board** | LLMOps engineer, platform engineer | Which agents changed behavior or need investigation? | Cost-per-run, anomaly counts, success rate, tool mix, drift score |
| **Trace Search** | Developer, operator | Can I find all runs matching this pattern? | Indexed span attributes, tags, cost, dates, status |

The principle is: if two teams instrument different frameworks but follow OTel semconv, they should land in the same mental model once they open the product.

### 2.1.2 v0.1.0 Interoperability Requirements

Interoperability is a product requirement, not an implementation detail.

| Interop target | Why it matters | v0.1.0 expectation |
|---|---|---|
| **OpenTelemetry Collector** | Standard ingest pipeline and vendor-neutral transport | Native OTLP export, documented collector config |
| **Tempo / Jaeger** | Existing trace backends most teams already run | First-class support and tested demo stacks |
| **Prometheus** | Fleet-level aggregation and alerting | Export metrics for anomaly counts, cost summaries, run outcomes |
| **Grafana** | Standard dashboarding and drill-down environment | Linkable dashboards and trace deep-links |
| **Alertmanager / webhooks** | Ops workflows need routing and ownership | Anomalies emitted as alert-friendly events |
| **GitHub / CI pipelines** | Version comparison becomes valuable at release boundaries | Version metadata attachable to traces from CI/CD |
| **Policy / approval systems** | Mature agents have governance touchpoints | Trace model must leave room for approval and policy overlays |

The product should never require users to replace their tracing backend to adopt it. Adoption becomes easier when `agent-exec-trace` behaves like an opinionated, agent-aware layer on top of infrastructure they already trust.

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

### 2.3.1 v0.2.0 Release Goal

**Goal:** move from a strong debugger to a usable operating surface for multiple agents.

v0.2.0 is where the product becomes clearly more than a trace viewer. The release should make it possible for a team to manage several agents over time, compare changes, understand cost behavior, and investigate decisions without dropping into raw backend tooling.

**What success looks like:**

- Teams can compare agent versions without custom notebooks
- Operators can search and group runs without knowing exact run IDs
- Cost is explainable at the run, agent, and workload level
- Memory behavior and human interventions are visible enough to review in incident and rollout meetings
- A second runtime adapter proves the model is not LangGraph-specific

### 2.3.2 v0.3.0 Backlog (Maturing Product)

| Feature | Priority | Why it matters now |
|---|---|---|
| **Multi-agent interaction maps** | P0 | Once teams adopt supervisor/subagent patterns, a single linear trace is not enough. They need a system view of agent-to-agent delegation. |
| **Approval / policy overlays** | P0 | Mature teams need to correlate behavior with governance boundaries: human approvals, deny decisions, escalation reasons. |
| **Drift scoring and baselines** | P0 | Operators need statistical baselines by agent, tool path, and workload, not just threshold-based alerts. |
| **Workload cohorts** | P1 | Compare behavior by request class, user segment, repository, environment, or task type. Useful for separating "agent got worse" from "inputs changed." |
| **Release-aware version compare** | P1 | Tie behavior deltas to commits, deployment windows, prompt versions, model changes, and tool schema changes. |
| **Exportable investigation packets** | P1 | Share a trace plus summary, anomalies, versions, and cost context as a reusable artifact for postmortems and reviews. |
| **Backend compatibility matrix** | P2 | Confirm what works with Tempo, Jaeger, Grafana, and vendor OTLP endpoints so adoption scales. |

**v0.3.0 release goal:** move from team-level debugging to organization-level operational review.

### 2.3.3 v0.4.0 Backlog (Mature Product)

| Feature | Priority | Why it matters at maturity |
|---|---|---|
| **Standardized investigation workflows** | P0 | Product should guide users through repeatable flows: investigate expensive run, compare release, review intervention-heavy agent, audit memory corruption. |
| **Reference semantic convention extensions** | P0 | Publish a stable extension package for loops, approvals, cost attribution, drift, and memory mutation while upstream OTel catches up. |
| **Governance-ready audit views** | P1 | Leadership and risk teams need views for approvals, tool writes, sensitive-memory access, and policy exceptions. |
| **Cross-system correlation** | P1 | Link agent traces to logs, incidents, deploys, feature flags, and service traces to answer "what else changed around this run?" |
| **Pluggable detectors** | P1 | Mature users want custom anomaly detectors for their own tool chains and behaviors without forking the product. |
| **Team operating packs** | P2 | Opinionated presets for common cases: coding agents, DevOps agents, support agents, RAG agents. |
| **OTel upstream contribution path** | P2 | By this point the product should have enough field evidence to propose stable upstream semconv additions backed by reference data and examples. |

**v0.4.0 release goal:** become the reference operational layer for agent traces in OTel-native environments.

### 2.4 Non-Goals (Will Not Build)

| Not building | Why |
|---|---|
| Full trace backend | Uses existing backends (Tempo, Jaeger). Not a replacement for them. |
| Evaluation framework | Shows *what happened*, not *whether it was correct*. Complements eval tools like EvalForge. |
| Prompt management or datasets | Langfuse territory. Stay focused on runtime observability. |
| SaaS/cloud-hosted version | Local-first OSS. Self-hosted only. |
| Policy enforcement engine | Observability, not governance. Integrates with policy tools but does not enforce. |

### 2.5 Architecture

### 2.5.1 Architecture Principles

| Principle | Why it exists |
|---|---|
| **OTel first** | If a concept can be expressed with existing OTel semconv, use it. Add extensions only when the standard is missing something important. |
| **Backend neutral** | Product must work with Tempo, Jaeger, and OTLP-compatible vendors. |
| **Views over raw queries** | Most users should succeed through standard views before they need advanced query tools. |
| **Interop over replacement** | Integrate with systems teams already run rather than trying to replace their tracing, dashboards, or alerting stack. |
| **Reference implementation mindset** | The SDK and example stacks should teach the ecosystem how OTel-native agent observability should look. |

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

### 2.6.1 Product Surface by Maturity Stage

| Stage | Product surface | Primary value |
|---|---|---|
| **v0.1.0** | SDK, OTLP export, run timeline, fleet board, anomaly detection | Make one bad run and one fleet understandable |
| **v0.2.0** | Version compare, search, cost attribution, memory audit, interventions, second runtime adapter | Make several agents manageable over time |
| **v0.3.0** | Multi-agent views, policy overlays, workload cohorts, release-aware comparison | Make org-scale operations and release reviews possible |
| **v0.4.0** | Standardized workflows, audit views, cross-system correlation, pluggable detectors | Make the product the operational home for agent trace investigations |

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

### 4.2.1 What Mature Products in Adjacent Categories Teach Us

Research across Tempo, Jaeger, and large observability products points to several maturity signals that matter here:

- **Queryless drill-down matters**: Grafana Tempo explicitly emphasizes point-and-click trace analysis, automatic comparison, and simplified visualizations. Mature products reduce dependence on expert query syntax.
- **Standard backends win adoption**: Jaeger and Tempo succeed because they fit existing OTel pipelines instead of forcing a net-new data plane.
- **Compatibility is part of the product**: Jaeger documents version compatibility and backend support policies. Mature observability tools make interop explicit.
- **Standard views beat bespoke dashboards**: RED views, service maps, and trace drill-down became sticky because teams could align around them. Agent observability needs the equivalent.

For `agent-exec-trace`, this means maturity is not just more features. It is:

1. Standardized operator views
2. Stable interop contracts
3. Clear release and support promises
4. Opinionated workflows that reduce investigation time

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

### 4.5 Standardized View Catalog

To avoid becoming a generic trace UI, the product should maintain a stable catalog of first-class views.

| View | Maturity target | Why it should exist |
|---|---|---|
| **Run Timeline** | v0.1.0 | The core behavioral story for a single run |
| **Run Summary** | v0.1.0 | A fast answer to cost, retries, tools, and interventions |
| **Fleet Health** | v0.1.0 | Triage multiple agents without clicking every run |
| **Version Compare** | v0.2.0 | Make rollout decisions evidence-based |
| **Search & Cohorts** | v0.2.0 | Investigate patterns across many runs |
| **Decision Inspector** | v0.2.0 | Explain why a choice was made |
| **Interaction Map** | v0.3.0 | Understand multi-agent delegation and fan-out |
| **Governance Review** | v0.3.0 | Surface approvals, denials, and policy boundaries |
| **Audit Lens** | v0.4.0 | Support mature review, compliance, and postmortem workflows |

These views should remain stable enough that teams can write playbooks against them.

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
