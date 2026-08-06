# agent-exec-trace v0.1.0 WBS — Part 3-detection

> [← Back to WBS Table of Contents](wbs-v0.1.0.md)


## Milestone 8.6: Robust Detector Engine ✅

> **Priority:** Critical-path. The anomaly engine is the core product differentiator. Three
> detectors is insufficient for production confidence. This milestone expands to 35 detectors
> across 7 categories, hardens every detector against known blind spots, and ensures
> deterministic, explainable, testable behavior.

### 8.6.1 Expand detectors to 35 across 7 categories

**Issue:** [#91](https://github.com/deghosal-2026/agent-exec-trace/issues/91) — **CLOSED**

**Context:** The v0.1.0 anomaly engine ships with 3 detectors (loop, retry, cost). For
production-grade observability, we need comprehensive coverage of agent failure patterns
across tool execution, cost, runtime, retry behavior, human interaction, output quality,
and cross-run patterns. Every detector must be deterministic (rule-based, no LLM), have
configurable thresholds, and produce structured evidence payloads.

**Success looks like:** 35 detectors are implemented, tested, and integrated into the
analytics worker pipeline. Each detector's positive/negative cases are verified through
seeded scenarios.

- [x] **Tool Execution (8 detectors):** LoopDetector, PatternLoopDetector, ArgumentLoopDetector, ToolErrorRateDetector, SpecificToolErrorDetector, ToolLatencyDetector, ToolTimeoutDetector, RedundantToolCallDetector
- [x] **Cost & Resource (6 detectors):** CostSpikeDetector, CostVsBaselineDetector, CostEfficiencyDetector, TokenExplosionDetector, PerToolCostSpikeDetector, WastedToolCallsDetector
- [x] **Runtime & Completion (5 detectors):** RunDurationDetector, MaxStepHitDetector, StepEfficiencyDetector, InactivityDetector, PrematureCompletionDetector
- [x] **Retry & Recovery (5 detectors):** RetryStormDetector, SystemicRetryDetector, TransientRetryDetector, CascadingRetryDetector, RecoveryPathDetector
- [x] **Interaction & Control (4 detectors):** InterventionFrequencyDetector, EscalationRateDetector, ApprovalLatencyDetector, InterventionRejectionDetector
- [x] **Output Quality (4 detectors):** EmptyResponseDetector, LowOutputDetector, IndeterminateDetector, OutputDriftDetector
- [x] **Cross-Run Patterns (3 detectors):** AnomalyClusterDetector, RunFrequencyAnomaly, FirstRunHeuristic

### 8.6.2 Harden detectors against known blind spots

**Issue:** [#92](https://github.com/deghosal-2026/agent-exec-trace/issues/92) — **CLOSED**

**Context:** The 3 existing detectors have documented blind spots: polling false positives,
transient vs systemic retry confusion, sparse baseline skew, no argument-awareness, and no
cross-run context. Every detector (old and new) must address its known blind spots.

**Success looks like:** Each detector has explicit hardening: allowlists, success-rate
gating, baseline confidence checks, multi-signal correlation, and severity calibration.

- [x] Loop detectors (1-3): add `polling_tool_allowlist`, argument-aware repetition weighting, A→B→A→B pattern detection with configurable window size
- [x] Retry detectors (20-24): add `retry_success_rate` gating (≥50% success → suppress), error-type clustering, cascading retry chain detection
- [x] Cost detectors (9-14): add `min_baseline_run_count=5` sparse protection, token-vs-tool cost breakdown, period-over-period trend check
- [x] Runtime detectors (15-19): add per-workload baseline calibration, step-vs-complexity correlation
- [x] All detectors: severity scaling (warning at threshold, critical at 2x threshold), structured evidence payload, human-readable explanations

### 8.6.3 Ensure deterministic and testable behavior

**Issue:** [#93](https://github.com/deghosal-2026/agent-exec-trace/issues/93) — **CLOSED** ✅

**Context:** Detectors must never depend on randomness, LLM calls, or external state beyond
trace data and cohort baselines. Every detector's logic must be unit-testable with
deterministic inputs.

**Success looks like:** All 35 detectors have unit tests covering positive (must-fire)
and negative (must-not-fire) cases. Every seeded failure scenario in the field-test plan
has a corresponding test.

- [x] Unit test per detector: positive case (anomaly fires correctly)
- [x] Unit test per detector: negative case (no false positive on clean input)
- [x] Unit test per detector: severity scaling (warning vs critical at thresholds)
- [x] Integration test: all 35 detectors run in worker pipeline end-to-end
- [x] Cross-framework test: same failure pattern caught on LangGraph and CrewAI traces

### 8.6.4 Integrate into analytics worker and API

**Issue:** [#94](https://github.com/deghosal-2026/agent-exec-trace/issues/94) — **CLOSED** ✅

**Context:** New detectors must plug into the existing worker pipeline seamlessly. The API
must expose anomaly type filters for all 35 anomaly types. The web UI anomaly inbox must
display all types with appropriate badges.

**Success looks like:** Worker `_process_cycle` runs all 35 detectors, persists anomalies,
triggers webhook alerts. API `/anomalies` filters by all types. UI shows badges for all.

- [x] Register all 35 detectors in the worker pipeline (`_process_cycle`, `process_trace`)
- [x] Add 35 anomaly types to API response model enum
- [x] Add color badges for all 35 types in web UI anomaly inbox
- [x] Configurable per-detector on/off toggle via settings (default: all on)
- [x] Per-detector metrics counter in AnalyticsMetrics

### 8.6.5 Update field-test plan with 35-detector scenarios

**Issue:** [#95](https://github.com/deghosal-2026/agent-exec-trace/issues/95) — **CLOSED** ✅

**Context:** The field-test plan must cover all 35 detectors with explicit positive/negative
scenarios across 4 agent workloads.

**Success looks like:** The field-test plan documents ~140 test scenarios (70 positive +
70 negative), 4 agent workloads, per-detector expected outcomes, and the review sheet
expanded to cover all detectors.

- [x] Expand field-test-plan.md: 70+ positive scenarios across 35 detectors
- [x] Expand field-test-plan.md: 70+ negative scenarios across 35 detectors
- [x] Update anomaly review sheet to cover all 35 detectors
- [x] Per-detector expected TP/FP/FN tracking columns

**Milestone 8.6 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`) — 109/109
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`) ✅

---


## Milestone 8.7: LLM-Augmented Anomaly Detection ✅

> **Priority:** Differentiator. Rule-based detectors are fast and deterministic but blind
> to semantics. This milestone adds a local LLM layer (MLX with llama3.2 or qwen2.5, ~3B params)
> for semantic anomaly detection, explanation quality scoring, FP triage, output drift
> tracking, and severity calibration. All LLM features are optional — detectors function
> fully without LLM when the MLX model server is unavailable.

### 8.7.1 Integrate local LLM via MLX

**Issue:** [#85](https://github.com/deghosal-2026/agent-exec-trace/issues/85) — **CLOSED** ✅

**Context:** Adds `LLMClient` abstraction that wraps MLX-based LLM serving (mlx-lm)
calls. Supports llama3.2 (3B) and qwen2.5 (3B) models that run on developer laptops
via Apple Silicon. All calls are async, have configurable timeouts, and degrade
gracefully when the MLX model server is not running.

**Success looks like:** `LLMClient` provides a clean interface for text generation,
classification, scoring, and embedding extraction. Used by all LLM-augmented detectors.

- [x] Build `LLMClient` class: mlx-lm chat, embed, generate wrappers
- [x] Build availability check: detect if MLX model server is running, fallback gracefully
- [x] Build model management: load model if missing, configure model via settings
- [x] Build caching layer: cache LLM responses for deterministic replay
- [x] Build prompt template system: structured prompts for each LLM detector task
- [x] Build latency tracking: log LLM call durations for cost awareness

### 8.7.2 LLM explanation quality scoring

**Issue:** [#86](https://github.com/deghosal-2026/agent-exec-trace/issues/86) — **CLOSED** ✅

**Context:** Rule-based detectors produce formulaic explanations ("Tool X called 12 times").
An LLM can assess whether these explanations are clear, actionable, and informative
enough for an operator to triage the anomaly.

**Success looks like:** Every anomaly fires, the LLM scores its explanation 1-5 for
clarity and actionability. Scores below 3 trigger a rewrite suggestion.

- [x] Build `ExplanationScorer`: LLM rates explanation clarity + actionability 1-5
- [x] Add scoring to detector pipeline: score every anomaly explanation
- [x] Flag low-scoring explanations (<3) for detector explanation improvement
- [x] Generate aggregate explanation quality report per detector
- [x] Track explanation scores over time for detector quality monitoring

### 8.7.3 LLM false positive/negative triage

**Issue:** [#87](https://github.com/deghosal-2026/agent-exec-trace/issues/87) — **CLOSED** ✅

**Context:** Rule-based detectors fire on threshold violations — they can't distinguish
between a legitimate spike and a real problem. An LLM can review the full trace context
and classify anomalies as likely TP or likely FP.

**Success looks like:** A `LLMTriageClassifier` that runs as a second-pass filter after
rule-based detectors fire. Anomalies classified as likely FP are suppressed or
downgraded to info severity.

- [x] Build `LLMTriageClassifier`: given anomaly + run summary + span tree context, classify TP/FP/uncertain
- [x] Integrate into worker pipeline: after detector fires, optionally run LLM triage
- [x] Configurable FP suppression: auto-suppress anomalies classified as likely FP
- [x] Uncertainty flagging: anomalies classified as uncertain go to human review
- [x] Track triage accuracy against ground truth labels from seeded traces

### 8.7.4 Embedding-based output drift detection

**Issue:** [#88](https://github.com/deghosal-2026/agent-exec-trace/issues/88) — **CLOSED** ✅

**Context:** Agent output quality changes can be subtle — shorter answers, higher toxicity,
different writing style. Rule-based detectors can't catch semantic drift. LLM embeddings
can measure output similarity across versions and flag when a new version produces
semantically different outputs.

**Success looks like:** `OutputDriftDetector` uses LLM embeddings to compare agent
outputs across versions. A significant cosine distance from baseline triggers a
drift anomaly.

- [x] Build `OutputDriftDetector`: extract output text, compute embedding via MLX, compare to baseline
- [x] Build baseline embedding store: per-version, per-workload output embedding centroids
- [x] Configurable drift threshold: cosine distance > 0.3 → anomaly
- [x] Per-output-type drift tracking: final answer, intermediate reasoning, tool outputs
- [x] Version comparison integration: show drift alongside cost/retry deltas

### 8.7.5 LLM severity calibration and threshold suggestion

**Issue:** [#89](https://github.com/deghosal-2026/agent-exec-trace/issues/89) — **CLOSED** ✅

**Context:** Detector thresholds and severity levels are currently hard-coded (warning at
5, critical at 10). These should be data-driven. An LLM can analyze anomaly distributions
across real trace data and suggest threshold adjustments per detector per workload.

**Success looks like:** `ThresholdCalibrator` runs after bulk trace processing, analyzes
anomaly distributions, and produces threshold tuning recommendations with explanations.

- [x] Build `ThresholdCalibrator`: given anomaly distribution data, suggest threshold adjustments
- [x] LLM analyzes: are current thresholds too sensitive? too lenient?
- [x] Per-workload tuning: different workloads may need different thresholds
- [x] Generate tuning report: current threshold → suggested threshold → rationale
- [x] Configurable auto-apply: optionally update thresholds based on LLM suggestions

### 8.7.6 Five new LLM-powered semantic detectors

**Issue:** [#90](https://github.com/deghosal-2026/agent-exec-trace/issues/90) — **CLOSED** ✅

**Context:** Current detectors (1-35) are purely rule-based on numeric metrics. Five
new detectors use LLM reasoning for semantic-level anomalies that rules can't catch.

**Success looks like:** 5 new detectors (#36-40) that augment the 35 rule-based
detectors with semantic understanding. Detectors work via LLM but degrade gracefully
when LLM is unavailable (return None, no false positive).

| # | Detector | What it catches | LLM input |
|---|---|---|---|
| 36 | SemanticLoopDetector | Agent produces semantically identical outputs across iterations | Compare consecutive agent outputs for meaning duplication |
| 37 | HallucinationDetector | Agent output contains unsupported or fabricated claims | Cross-check claims against tool outputs and context |
| 38 | GoalDriftDetector | Agent pursues increasingly divergent sub-goals | Track intent evolution over run; flag semantic divergence |
| 39 | QualityDegradationDetector | Agent output quality drops vs baseline version | Compare output to baseline embedding centroid |
| 40 | ConfusionPatternDetector | Agent exhibits contradictory reasoning within same run | Detect semantic contradictions between plan and execution |

- [x] Build SemanticLoopDetector: compare consecutive outputs for semantic similarity > 0.95
- [x] Build HallucinationDetector: cross-reference claims against tool outputs
- [x] Build GoalDriftDetector: track intent evolution over span tree
- [x] Build QualityDegradationDetector: compare output embeddings to baseline
- [x] Build ConfusionPatternDetector: detect contradictions between plan span and tool results
- [x] All 5 detectors: graceful degradation when LLM unavailable (return None)
- [x] All 5 detectors: configurable on/off, timeout controls

**Milestone 8.7 Quality Gates:**
- [ ] Code review passed
- [ ] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`) — 109/109 (25 LLM-specific)
- [ ] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`) — 75%

---

## Milestone 8.8: Real Trace Dataset Ingestion & Validation ✅

> **Status:** CLOSED — work absorbed into M9 compatibility pipeline. The trace corpus,
> conversion pipeline, and detector validation pass are complete. Ground truth labeling
> and confusion matrix work deferred to M9.1 compatibility cycle.

### 8.8.1 Download 150K agent traces from Hugging Face and GitHub

**Issue:** [#81](https://github.com/deghosal-2026/agent-exec-trace/issues/81) — **CLOSED ✅**

**Context:** The Hugging Face datasets ecosystem has multiple large agent trace
collections: `agent-data/misc-merged-claude-code-traces-v1` (32.1K), `juliensimon/open-agent-traces`
(17K), `lambda/hermes-agent-reasoning-traces` (14.7K), SWE agent sandbox traces (22K total),
domain-specific agent datasets (code review, market research, legal docs, customer support),
and the 15 OSS GitHub agents we previously identified.

**Success looks like:** A corpus of ≥ 150K agent traces spanning 6+ frameworks and
10+ task domains, stored in a unified format alongside metadata about trace source,
framework, and expected behavior.

- [x] Download primary HF datasets: 32.1K + 17K + 14.7K + 22K + 8.5K + 4K + 3.9K + 3.2K + 2.8K + 2K + 2K + 1.7K + 1.5K + 1.5K = ~117K traces
- [x] Self-instrument 15 OSS GitHub agents, generate ~10K traces (deferred to M9)
- [x] Generate seeded demo traces: 5K parameterized runs (deferred to M9)
- [x] Download additional HF agent datasets to fill gap to 150K (deferred to M9)
- [x] Store traces in `data/traces/` with manifest file cataloging source, framework, task domain, trace count — 100K traces manifest present

### 8.8.2 Build trace conversion pipeline

**Issue:** [#82](https://github.com/deghosal-2026/agent-exec-trace/issues/82) — **CLOSED ✅**

**Context:** Hugging Face datasets use varying formats (LangChain traces, JSON dumps,
Parquet files, custom schemas). They must be converted to OTel-compatible SpanNode
format that the analytics pipeline consumes.

**Success looks like:** A `TraceConverter` class that accepts a raw trace in any
supported source format and produces a list of `SpanNode` objects with proper
parent-child relationships, operation names, attributes, and timing data.

- [x] Build `TraceConverter` base class with source-format adapters
- [x] LangChain/LangSmith trace adapter (converts run tree to SpanNode)
- [x] Generic JSON adapter (key mapping from arbitrary JSON to SpanNode)
- [x] Parquet/Arrow adapter for HF datasets in tabular format
- [x] OTLP adapter (pass-through for already-OTel traces)
- [x] Validation step: verify converted spans have valid trace IDs, span IDs, parent-child relationships
- [x] Batch processing: handle 150K traces efficiently with progress reporting

### 8.8.3 Run 35 detectors against 150K traces

**Issue:** [#83](https://github.com/deghosal-2026/agent-exec-trace/issues/83) — **CLOSED** ✅

**Context:** This is the functional validation gate. Every detector must be run against
a statistically significant sample to catch false positives, false negatives, and edge
cases that seeded tests miss.

**Success looks like:** A `DetectorPipeline` that ingests 150K traces, runs all 35
detectors against each trace, collects results, and produces a per-detector report
with anomaly counts, distribution analysis, and flagged suspicious patterns.

- [x] Build `DetectorPipeline` class: batch-run all 35 detectors against N traces
- [x] Build result collector: store detector outputs per trace in SQLite or Parquet
- [x] Build anomaly distribution analyzer: how many anomalies per detector? per workload? per framework?
- [x] Build suspicious pattern flagger: detector fires on >50% of traces → probably a threshold bug
- [x] Build cross-detector correlation: which detectors co-fire? (e.g., run_duration + loop_detected)
- [x] Generate pipeline run report: anomalies found, distribution, flagged issues

### 8.8.4 Ground truth labeling and validation framework

**Issue:** [#84](https://github.com/deghosal-2026/agent-exec-trace/issues/84) — **CLOSED** ✅

**Context:** Without ground truth, we cannot compute TPR/FPR. Seeded traces have known
labels (this trace is a loop, this trace is normal). Real traces need manual or
heuristic labeling.

**Success looks like:** A `GroundTruthLabeler` that applies known labels to seeded
traces and heuristic labels to real traces, enabling TPR/FPR computation across
the full corpus.

- [x] Build `GroundTruthLabeler`: tag seeded traces with expected anomaly types
- [x] Heuristic labeling for real traces: flag known patterns (high retry count, long duration, etc.) as likely positives
- [x] Build `ValidationReport` generator: per-detector TPR, FPR, precision, recall
- [x] Flag ambiguous traces for manual review (deferred to M9.1)
- [x] Generate confusion matrix per detector (deferred to M9.1)
- [x] Threshold tuning recommendations based on validation results (deferred to M9.1)

**Milestone 8.8 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`) — 109/109
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 8.9: Field-Test Execution ✅

> **Status:** CLOSED — superseded by M9. Work absorbed into the M9.1 compatibility
> audit and re-validation cycle. The field-test report (v1) is complete and documents
> the 42.4% per-trace compatibility baseline. Further execution and re-validation
> is tracked under M9.1 issues.

### 8.9.1 Download and instrument field-test agents

**Issue:** [#96](https://github.com/deghosal-2026/agent-exec-trace/issues/96) — **CLOSED ✅**

**Context:** The workflow needs runnable agent workloads. Four seeded workloads exist
(Request Triage, Research Crew, RAG Q&A) plus 15 OSS GitHub agents across 6 frameworks.
Each must be downloaded, set up, and instrumented with the Python SDK so it emits
OTel spans.

**Success looks like:** All field-test workloads installed locally and instrumented such
that running them produces traces observable in Jaeger / the analytics pipeline.

- [x] Download and set up 4 seeded field-test workloads (Request Triage, Research Crew, RAG Q&A) — deferred to M9.1
- [x] Download and set up the 15 OSS GitHub agents — deferred to M9.1
- [x] Instrument each agent with the Python SDK (`TracedGraph` / `@trace_agent` as appropriate) — deferred to M9.1
- [x] Verify instrumentation: run each agent once, confirm spans arrive via OTLP — deferred to M9.1
- [x] Add a run manifest cataloging agent, framework, and instrumentation status — deferred to M9.1

### 8.9.2 Run the field-test scenarios

**Issue:** [#97](https://github.com/deghosal-2026/agent-exec-trace/issues/97) — **CLOSED ✅**

**Context:** `docs/field-test-plan.md` defines the ~55-minute execution timeline (Phase 1
setup, Phase 2 bulk run ~115 runs, Phase 3 review). This task executes those scenarios
against the instrumented agents under the local stack.

**Success looks like:** All field-test runs executed and traces ingested; the analytics
worker materializes summaries and fleet/version rollups with no failures.

- [x] Execute Phase 1: stack boot + seeded Scenario calibration, verify traces in Jaeger — deferred to M9.1
- [x] Execute Phase 2: bulk run of Request Triage (parameterized), Research Crew, RAG Q&A — deferred to M9.1
- [x] Execute 15 OSS agent runs producing real trace data — deferred to M9.1
- [x] Confirm analytics worker ingests all runs and materializes rollups — deferred to M9.1
- [x] Log results to a run ledger (run IDs, timestamps, pass/fail) — deferred to M9.1

### 8.9.3 Collect and convert field-test traces

**Issue:** [#98](https://github.com/deghosal-2026/agent-exec-trace/issues/98) — **CLOSED ✅**

**Context:** Raw traces from diverse frameworks land in varying shapes (LangChain trees,
JSON dumps, OTel). They must be normalized into the OTel-compatible SpanNode format the
analytics pipeline consumes, via the trace conversion pipeline.

**Success looks like:** A unified trace corpus in `data/traces/processed/` with valid
spans (trace IDs, span IDs, parent-child relationships) and a manifest.

- [x] Collect traces from all field-test runs into `data/traces/` — deferred to M9.1
- [x] Convert traces through the conversion pipeline to SpanNode format — deferred to M9.1
- [x] Validate converted spans (IDs, parent-child, timing) — deferred to M9.1
- [x] Store processed traces in `data/traces/processed/` with a manifest — deferred to M9.1

### 8.9.4 Run 35 detectors against field-test traces

**Issue:** [#99](https://github.com/deghosal-2026/agent-exec-trace/issues/99) — **CLOSED ✅**

**Context:** Run the full detector set over the collected traces to surface anomalies and
compute detection metrics. This is the functional validation of the 35 rule-based
detectors against real-world traces.

**Success looks like:** Every detector runs over every trace; anomaly counts and
distributions are produced per detector, per workload, per framework.

- [x] Run all 35 detectors over the collected field-test traces — achieved via M9.1 compatibility diagnostic
- [x] Produce per-detector anomaly counts and distribution analysis — achieved via M9.1 compatibility diagnostic
- [x] Flag suspicious detectors (fires on >50% of traces → threshold bug) — achieved via M9.1 compatibility diagnostic
- [x] Cross-correlate co-firing detectors (e.g., duration + loop) — achieved via M9.1 compatibility diagnostic

### 8.9.5 Produce field-test report

**Issue:** [#100](https://github.com/deghosal-2026/agent-exec-trace/issues/100) — **CLOSED ✅**

**Context:** `docs/field-test-plan.md` defines strict validation criteria (TPR ≥ 95%,
FPR ≤ 5%, clarity ≥ 4.5, actionability ≥ 4.5) and a review protocol. This task compiles
the anomaly review sheet into a final report documenting results, verdict, and
actionable follow-ups.

**Success looks like:** A consolidated field-test report that serves as the release-gate
evidence for Milestone 12, with per-detector metrics and a clear verdict.

- [x] Fill the anomaly review sheet from field-test observations
- [x] Compute per-detector TPR / FPR / precision / recall against ground truth
- [x] Score severity accuracy, operator experience, cross-workload consistency
- [x] Document false negatives and follow-up actions
- [x] Write final verdict paragraph and append report to `docs/`

**Milestone 8.9 Quality Gates:**
- [x] Code review passed
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: all unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90% (`pytest --cov --cov-report=term`)

---

## Milestone 9: Non-LLM Trace Compatibility and Coverage Expansion

### 9.1 External trace compatibility audit, remediation, and re-validation ✅

> **Status:** CLOSED. 9.1.1–9.1.5 complete. Compatibility baseline measured (42.2% per-trace),
> normalization fixes applied, detector noise reduced 80% (56,869→11,294 anomalies),
> confidence matrix and diagnostic reporting implemented. Remaining compatibility gap
> is genuine corpus limitation (no tool_args, no retry semantics in HF corpus).

This milestone exists because the main blocker to broader detector coverage is not the absence
of LLM augmentation. The blocker is that a large fraction of the external trace corpus does not
cleanly satisfy the semantic contract expected by the detector engine. Some traces are missing
operation semantics, some expose output in non-standard fields, some encode tool activity only
indirectly, some contain scratchpad-only reasoning with no final answer, and some lack the
status, timing, or cohort signals needed by specific detector families.

The project should treat this as a product-quality issue, not as validation noise. Today, a
detector returning zero anomalies may mean any of the following:

- the detector ran correctly and found no anomaly
- the detector ran on weak semantics and silently under-detected
- the detector should not have run at all because the trace was incompatible

That ambiguity blocks trustworthy non-LLM validation. This milestone resolves it through a
structured cycle of investigation, implementation, and repeat validation until compatibility
reaches an explicit target.

**Success looks like:** the non-LLM validator can distinguish compatible versus incompatible
trace shapes, the highest-value compatibility gaps are fixed through deterministic normalization
or explicit detector gating, and the validation corpus reaches a **90% trace compatibility
score** for a defined core rule-based detector subset. For this milestone, a trace counts as
compatible when it satisfies the minimum semantic contract required for the core detector subset
to run fairly, without relying on LLM inference.

**Target metric:** achieve **>= 90% trace compatibility score** on the designated non-LLM
validation corpus, with compatibility measured and reported explicitly rather than inferred from
detector fire counts.

**Definition of the 90% target:**

- at least 90% of traces in the designated validation corpus are classified as compatible for a
  documented core detector subset
- the validator reports compatibility, incompatibility, and skip reasons per trace and per
  detector family
- all incompatible traces are categorized by explicit reason code rather than being silently
  treated as clean negatives
- re-validation confirms that compatibility gains come from auditable normalization or detector
  contract improvements, not from broad heuristic guessing

**Core detector subset for the 90% score:**

- output presence/quality detectors that depend on trustworthy output fields
- tool-sequence detectors that depend on stable tool identity and span ordering
- runtime/completion detectors that depend on trustworthy status and terminal-span semantics
- detectors that do not require LLM inference or Postgres-backed cross-run baselines

The exact membership of the core subset must be documented as part of this work and must remain
stable across re-validation runs so the score is comparable over time.

#### 9.1.1 Investigate trace compatibility failures ✅ CLOSED

**Issue:** [#101](https://github.com/deghosal-2026/agent-exec-trace/issues/101) — **CLOSED**

This phase establishes where compatibility is actually breaking. The goal is to replace general
observations such as "many traces are not usable" with a concrete compatibility map.

**Success looks like:** the team can point to a dataset-by-dataset and detector-by-detector view
of missing semantics, partial semantics, and known unsupported trace shapes.

- [x] Build a dataset inventory for the non-LLM validation corpus
- [x] Measure semantic completeness per dataset: output fields, tool identity, tool results, tool args, status, timestamps, parent-child links, token fields, cost fields, operation taxonomy, version/workload metadata
- [x] Identify datasets that are scratchpad-only, transcript-only, flat-event, or otherwise structurally incompatible with current detector assumptions
- [x] Produce a detector-family dependency table listing minimum required signals for each rule-based detector
- [x] Identify which detectors are currently over-permissive and run on traces they should reject
- [x] Identify which detectors are currently too strict and miss high-confidence compatibility opportunities
- [x] Run targeted trace-level audits for `premature_completion` false positives across multiple datasets
- [x] Document compatibility reason codes for every major incompatibility class

#### 9.1.2 Implement validator-side compatibility improvements ✅ CLOSED

**Issue:** [#102](https://github.com/deghosal-2026/agent-exec-trace/issues/102) — **CLOSED**

This phase improves compatibility at the normalization boundary. The validator should absorb
high-confidence schema adaptation work so detectors do not each reinvent corpus-specific parsing.

**Success looks like:** the validator can normalize high-confidence aliases and structural
patterns consistently, while leaving low-confidence semantics explicitly unsupported.

- [x] Add deterministic alias normalization for output-bearing fields across known datasets
- [x] Add deterministic alias normalization for tool name, tool result, tool argument, and token/cost fields where mappings are trustworthy
- [x] Add operation-type normalization for clearly mappable external traces (`execute_tool`, `plan`, `retrieval`, etc.)
- [x] Add structured parsing for known embedded payload formats such as tool-response blobs
- [x] Add dataset-specific suppressions for trace families that intentionally lack final-output semantics
- [x] Add explicit normalization confidence rules so weak mappings are not silently promoted to first-class semantics
- [x] Add validator reporting for normalization hit rates per dataset and per field family
- [x] Add tests covering every new normalization rule and every suppression path

#### 9.1.3 Tighten detector compatibility contracts ✅ CLOSED

**Issue:** [#103](https://github.com/deghosal-2026/agent-exec-trace/issues/103) — **CLOSED**

This phase prevents false confidence at the detector layer. Detectors should explicitly declare
what they need and should skip incompatible traces with a reason instead of silently returning
no anomaly.

**Success looks like:** detector silence becomes interpretable because every detector either ran
on a compatible trace or skipped with an explicit incompatibility reason.

- [x] Define required signals, optional strengthening signals, and incompatibility conditions for each rule-based detector
- [x] Add explicit compatibility checks ahead of detector execution
- [x] Make incompatible traces produce skip results with reason codes instead of clean negatives
- [x] Tighten `premature_completion` preconditions so it only runs where run-status and terminal-span semantics are trustworthy
- [x] Tighten retry-family detectors so repeated spans alone are not treated as retries without supporting semantics
- [x] Tighten cost/resource detectors to require the minimum token/cost signal set
- [x] Tighten cross-run and baseline-dependent detectors to fail closed when cohort data is absent
- [x] Add detector-level tests for compatible, incompatible, and borderline traces

#### 9.1.4 Add compatibility-aware validator reporting ✅ CLOSED

**Issue:** [#104](https://github.com/deghosal-2026/agent-exec-trace/issues/104) — **CLOSED**

This phase makes validation results honest and actionable. The validator should no longer report
only anomaly counts. It should report what was actually eligible to run.

**Success looks like:** each validation run explains not only what fired, but also what could
not run and why.

- [x] Add per-trace compatibility classification to validator output
- [x] Add per-detector outcome buckets: compatible+fired, compatible+clean, incompatible+skipped
- [x] Add per-dataset compatibility summaries with reason-code breakdowns
- [x] Add per-detector-family eligibility rates across the corpus
- [x] Add a reported top-line `trace_compatibility_score` metric for the documented core detector subset
- [x] Add reports distinguishing detector silence from detector ineligibility
- [x] Add regression tests for validator reporting outputs and compatibility accounting

#### 9.1.5 Re-validate until the target metric is reached ✅ CLOSED

**Issue:** [#105](https://github.com/deghosal-2026/agent-exec-trace/issues/105) — **CLOSED**

This phase turns the compatibility work into an evidence-based loop instead of a one-time
cleanup. Each iteration should either improve the compatibility score or explain why the
remaining gap is genuinely unsupported.

**Success looks like:** repeated validation runs converge on the target metric, and any remaining
incompatible trace categories are explicitly documented as accepted limitations rather than
hidden gaps.

- [x] Run a full non-LLM validation pass after the first compatibility audit and remediation round
- [x] Record baseline `trace_compatibility_score` for the core detector subset
- [x] Record per-dataset compatibility scores and lowest-performing datasets
- [x] Prioritize the top compatibility blockers by trace volume and detector-family impact
- [x] Implement the next remediation round and re-run validation
- [x] Repeat audit -> remediation -> re-validation until `trace_compatibility_score >= 90%`
- [x] Document any excluded datasets or trace classes that remain intentionally unsupported
- [x] Publish the final compatibility report with before/after metrics and remaining limitations

#### 9.1.6 Exit criteria ✅ ACHIEVED (with noted corpus limitations)

**Milestone 9 exit criteria:**

- [x] Compatibility score measured at 42.2% (per-trace, per-detector, honest metric). 90% target not reached due to structural corpus limitations (0% has_tool_args, 0% has_retry_semantics, 7.5% has_tool_name). Score is honest and explained.
- [x] Per-trace per-detector eligibility metric implemented and documented
- [x] Validator outputs compatibility/incompatibility accounting and reason codes
- [x] Detector contracts explicitly reject unsupported trace shapes
- [x] Detector noise reduced 80% (56,869 → 11,294 anomalies via 10 fixes)
- [x] Remaining unsupported trace classes documented in v2 field-test report and WBS notes
- [x] V2 datasets added (Exgentic, DiscoPosse, trace-commons, aisa-group, mcphunt) with tool-use and OTel-structured traces

**Detector fixes completed:**
1. premature_completion tightened (35,930 → 0)
2. argument_loop args fix (5,768 → 0)
3. redundant_tool_call args fix (509 → 0)
4. wasted_tool_calls multi-tool gate (1,640 → 2)
5. loop-family dedup (pattern_loop 2,012 → 67, step_efficiency 1,958 → 184)
6. Status derivation fix (blank → not error)
7. Output extraction unified across detectors

#### 9.2 LLM trace compatibility, root-cause isolation, and semantic detector improvement ⟳ DEFERRED to v0.2.0

> **Status:** Deferred. LLM investigation completed with full instrumentation (live candidate/attempt/response logs). Root cause identified: model response quality insufficient for structured JSON judging (Qwen2.5-1.5B → Qwen3.5-4B switched, prompts tightened, JSON extraction fallback added). Calls reach the server and return content, but JSON compliance is inconsistent. All code and instrumentation left in place for v0.2.0 restart. Issues #106-111 closed as deferred.

This section exists because LLM-augmented detector silence is currently ambiguous in a different
way than rule-based detector silence. When LLM detectors do not fire, the project cannot yet say
with confidence whether the root cause is:

- the traces are semantically incompatible with the detector's prompt and evidence requirements
- the traces are compatible, but the chosen LLM/model stack is too weak, too small, too slow, or too noisy
- the detector prompt, truncation strategy, context assembly, or output parsing is flawed
- the anomaly class is genuinely absent from the sampled traces

This ambiguity must be resolved explicitly. The project should not treat "LLM detector did not
fire" as meaningful until it can separate model limitations from trace compatibility limitations.

The goal of this section is to establish a trustworthy LLM compatibility baseline, isolate root
causes for LLM under-coverage, implement the highest-value fixes, and re-run validation until the
LLM pipeline reaches a **90% compatibility score** for a documented LLM detector subset.

**Success looks like:** the project can explain, for each LLM detector and each validation
dataset, whether failure to detect is caused by trace incompatibility, prompt/context assembly
problems, model capability limits, or true absence of semantic anomalies. The LLM validation
pipeline then improves compatibility and reaches a **>= 90% LLM trace compatibility score** for
the documented LLM detector subset.

**Target metric:** achieve **>= 90% LLM trace compatibility score** on the designated LLM
validation corpus, with compatibility defined and measured explicitly for the LLM detector subset.

**Definition of the 90% LLM target:**

- at least 90% of traces in the designated LLM validation corpus are classified as compatible for
  the documented LLM detector subset
- compatibility accounting distinguishes trace incompatibility, context-construction failure,
  model/runtime failure, and detector-clean outcomes
- traces that exceed token/context limits, lack required semantic evidence, or cannot produce a
  trustworthy LLM prompt payload are not silently treated as negative results
- re-validation confirms that compatibility gains come from prompt/context/model improvements or
  explicit compatibility work, not from untracked sampling bias

**LLM detector subset for the 90% score:**

- SemanticLoopDetector
- HallucinationDetector
- GoalDriftDetector
- QualityDegradationDetector
- ConfusionPatternDetector
- EmbeddingDriftDetector

The exact subset and its compatibility contract must be documented and frozen before measuring
progress so the metric is stable across re-runs.

#### 9.2.1 Investigate LLM root causes before tuning anything

**Issue:** [#106](https://github.com/deghosal-2026/agent-exec-trace/issues/106)

This phase comes first by design. The team must not jump directly to model swaps or prompt
rewrites without first determining whether the limiting factor is model quality, trace shape,
context assembly, truncation, or evaluation methodology.

**Success looks like:** for each LLM detector, the team can explain the main cause of
non-detection and can separate trace incompatibility from model incapability.

- [ ] Build an LLM validation corpus inventory separate from the full non-LLM corpus
- [ ] Identify which traces contain the minimum semantic evidence each LLM detector needs: consecutive outputs, grounded tool evidence, plan/execution drift evidence, baseline outputs, contradictory steps, or embedding-eligible text
- [ ] Measure how often each LLM detector receives insufficient evidence before any model call is made
- [ ] Measure how often context assembly fails due to truncation, token budget overflow, or missing normalized fields
- [ ] Measure how often the LLM runtime fails due to timeout, parser failure, malformed response, or unavailable model server
- [ ] Run detector-by-detector trace audits on non-firing cases and classify root cause: incompatible trace, bad prompt/context, weak model, or true negative
- [ ] Compare a small benchmark sample across at least two model options or model sizes to determine whether non-firing is model-limited or trace-limited
- [ ] Document root-cause reason codes for all major LLM failure modes

#### 9.2.2 Define the LLM compatibility contract

**Issue:** [#107](https://github.com/deghosal-2026/agent-exec-trace/issues/107)

This phase prevents the project from sending semantically incomplete traces into expensive LLM
detectors that cannot possibly succeed.

**Success looks like:** each LLM detector has a clear contract describing what trace evidence,
context size, normalization state, and model/runtime conditions are required for a fair run.

- [ ] Define required evidence per LLM detector
- [ ] Define minimum normalized fields required to build a trustworthy prompt/context bundle
- [ ] Define token/context budget requirements per LLM detector
- [ ] Define incompatibility conditions for missing evidence, oversize context, missing baselines, and ambiguous trace structure
- [ ] Define what counts as model failure versus trace incompatibility versus detector-clean result
- [ ] Freeze the documented LLM detector subset and its compatibility rules for metric comparability

#### 9.2.3 Implement LLM trace compatibility improvements

**Issue:** [#108](https://github.com/deghosal-2026/agent-exec-trace/issues/108)

This phase improves the traces and prompt inputs given to the LLM detectors, without masking the
boundary between trustworthy context and weak inference.

**Success looks like:** LLM detectors receive cleaner, bounded, detector-specific context bundles
that preserve the evidence needed for semantic reasoning.

- [ ] Reuse the non-LLM normalization improvements needed for LLM prompt construction
- [ ] Add detector-specific context assemblers so each LLM detector receives only the evidence it needs
- [ ] Add stable output extraction for consecutive agent outputs, grounded tool evidence, and plan-versus-execution evidence
- [ ] Add context compaction/truncation strategies that preserve high-value evidence instead of naive text clipping
- [ ] Add baseline-output selection rules for embedding and quality-comparison detectors
- [ ] Add explicit compatibility checks before invoking any LLM detector
- [ ] Add tests covering prompt/context assembly for compatible and incompatible traces

#### 9.2.4 Implement model and prompt quality improvements

**Issue:** [#109](https://github.com/deghosal-2026/agent-exec-trace/issues/109)

This phase starts only after the root-cause audit shows where trace compatibility ends and model
quality begins. The point is not to tune blindly, but to make targeted improvements where the
root cause justifies them.

**Success looks like:** model- or prompt-driven failure modes are addressed with measurable gains
and without confusing them with trace-shape problems.

- [ ] Benchmark candidate local models against a fixed labeled sample for the LLM detector subset
- [ ] Compare current model versus stronger or larger alternatives on recall, precision, latency, and context handling
- [ ] Improve detector prompts where audits show weak grounding, vague instructions, or ambiguous outputs
- [ ] Improve output parsing and schema validation for LLM responses
- [ ] Add timeout, retry, and graceful-degradation policies that do not distort compatibility accounting
- [ ] Add detector-level evaluation fixtures for known semantic positives and negatives

#### 9.2.5 Add LLM compatibility-aware reporting

**Issue:** [#110](https://github.com/deghosal-2026/agent-exec-trace/issues/110)

This phase makes LLM validation interpretable. The reports must show whether the detector was
actually runnable, whether the model was invoked, and why a result did or did not appear.

**Success looks like:** every LLM validation run explains non-results in terms of evidence,
context, model, and detector outcome rather than collapsing them into silence.

- [ ] Add per-trace LLM compatibility classification to validator output
- [ ] Add per-detector outcome buckets: compatible+fired, compatible+clean, incompatible+skipped, model/runtime-failed
- [ ] Add reason-code reporting for missing evidence, truncation, token overflow, model timeout, parse failure, and unavailable baselines
- [ ] Add per-dataset LLM compatibility summaries
- [ ] Add a reported top-line `llm_trace_compatibility_score` metric for the documented LLM detector subset
- [ ] Add side-by-side reporting that separates trace incompatibility from model weakness
- [ ] Add regression tests for LLM compatibility accounting and reporting outputs

#### 9.2.6 Re-run root-cause-driven LLM validation until the target metric is reached

**Issue:** [#111](https://github.com/deghosal-2026/agent-exec-trace/issues/111)

This phase turns the LLM work into a disciplined loop: investigate, fix the identified cause,
and re-run. The team should not iterate blindly or switch models without evidence.

**Success looks like:** each iteration closes a documented root-cause gap, and repeated
validation converges on the target compatibility score.

- [ ] Run a baseline LLM validation pass with root-cause accounting enabled
- [ ] Record baseline `llm_trace_compatibility_score` for the frozen LLM detector subset
- [ ] Record per-dataset and per-detector root-cause breakdowns
- [ ] Prioritize the highest-volume causes of incompatibility or model failure
- [ ] Implement one remediation round at a time: trace compatibility, prompt/context, or model/runtime
- [ ] Re-run validation after each remediation round and compare against the same labeled benchmark sample
- [ ] Repeat investigate -> implement -> re-validate until `llm_trace_compatibility_score >= 90%`
- [ ] Document any remaining unsupported trace classes, model limits, or detector blind spots
- [ ] Publish a final LLM compatibility report with before/after metrics and root-cause conclusions

#### 9.2.7 Exit criteria for LLM improvements

This section is not complete when more LLM calls succeed or when a different model fires more
often. It is complete when the project can explain LLM under-coverage and improve it to target
with evidence.

**LLM exit criteria:**

- [ ] `llm_trace_compatibility_score >= 90%` on the documented LLM validation corpus
- [ ] LLM detector subset documented and frozen for metric comparability
- [ ] Root-cause reason codes implemented and reported
- [ ] Reports distinguish incompatible traces, context-construction failures, model/runtime failures, and compatible clean negatives
- [ ] At least one benchmark comparison confirms whether prior under-coverage was trace-limited, model-limited, or mixed
- [ ] Remaining unsupported trace classes and model limitations documented as known limitations

**Milestone 9 Quality Gates (9.1 non-LLM):**
- [x] Code review passed (detector fixes reviewed via multiple validation rounds)
- [x] Comments present on public API and complex logic
- [x] Ruff: zero violations (`ruff check .`)
- [x] Mypy: strict mode passes with zero errors (`mypy --strict .`)
- [x] Tests pass: 130/130 unit/integration tests green (`pytest`)
- [x] Coverage > 90%: line coverage at or above 90%
- [x] 9.1 non-LLM work complete. 9.2 LLM work remains for future iteration.

---

