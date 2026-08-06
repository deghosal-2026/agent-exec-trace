# Field-Test Plan — Anomaly Detection v0.1.0 (35 Detectors)

Anomaly detection in v0.1.0 is seeded and deterministic. This field test gates production
confidence for v1.0 by validating all 35 detectors against multiple frameworks, workloads, and
failure modes under strict metrics.

The plan covers 7 detector categories with at least 2 positive and 2 negative scenarios per
detector (70+ positive, 70+ negative total). A recipe appendix provides detailed trace-construction
instructions for detectors that depend on cohorts, cross-run state, or timed interactions.

## Pre-Flight: Detector Hardening

Before field test execution, harden detectors against known blind spots:

| Detector | Blind spot | Hardening |
|---|---|---|
| **LoopDetector** | False positives for intentional polling tools | Add `polling_tool_allowlist` config. Tools in the allowlist skip loop detection. |
| **RetryStormDetector** | No distinction between transient retries (succeeded) vs systemic (all failed) | Add `retry_success_rate` check. If ≥ 50% of retries ultimately succeeded, downgrade severity to `info` or suppress. |
| **CostSpikeDetector** | Sparse baseline (1-2 runs skews average) | Add `min_baseline_run_count` (default 5). Skip relative check if baseline cohort has fewer runs. |
| **ToolLatencyDetector** | One slow call in a heavy workload is not a spike | Compare against own-run average, not global. Multiplier-based (default 3.0x). |
| **TokenExplosionDetector** | Normal token growth in multi-step reasoning | Compare early-half vs late-half token counts; requires ≥4 spans and both halves non-empty. |
| **EscalationRateDetector** | High tool count without interventions is normal | Requires at least one intervention; compares intervention-to-tool ratio. |
| **FirstRunHeuristicDetector** | Every new agent version triggers a false positive | Silently returns None if the previous version cohort is empty or too small (v1+ threshold). |
| **OutputDriftDetector** | Short outputs are inherently variable | Skip when baseline output length < 50 chars; use deviation_multiplier (default 3.0x). |

## Agent Workloads

### Core Demo Workloads

| # | Agent | Framework | Adapter | What it does | Runs |
|---|---|---|---|---|---|
| 1 | **Request Triage** (seeded) | LangGraph | TracedGraph | Classifies support requests, searches KB, looks up accounts | 15 |
| 2 | **Request Triage** (parameterized) | LangGraph | TracedGraph | Same agent with 10+ randomized input batches | 40 |
| 3 | **Research Crew** | CrewAI | @trace_agent | 3-agent crew: Researcher → Analyst → Writer | 30 |
| 4 | **RAG Q&A** | LangGraph | TracedGraph | Retrieval-augmented Q&A with hallucination retries | 30 |
| | | | | **Total** | **~115** |

### OSS Agent Fleet (cross-framework validation)

| # | Agent | Framework | Runs |
|---|---|---|---|
| 5 | **AutoGen Math Solver** | AutoGen | 6 |
| 6 | **Browser-Use Web Agent** | browser-use | 6 |
| 7 | **Aider Code Editor** | aider | 6 |
| 8 | **SuperAGI Task Agent** | SuperAGI | 6 |
| 9 | **OpenAI Agents SDK** | OpenAI Agents | 6 |
| 10-19 | **10 additional GH agents** | various | 6 each |
| | | **Cross-framework total** | **~90** |

The parameterized Request Triage batch (40 runs) and the 15-agent OSS fleet (~90 runs) provide
the multi-run baseline cohorts needed by cross-run and baseline-dependent detectors.

## Detector → Workload Matrix

Which workloads are best suited to trigger (T) or avoid (A) each detector:

| # | Detector | RT-seeded | RT-param | Research Crew | RAG Q&A | OSS fleet | Threshold |
|---|----------|-----------|----------|---------------|---------|-----------|-----------|
| 1 | LoopDetector | T | T | T | T | T | 5 consec |
| 2 | PatternLoopDetector | T | T | — | T | — | window=4 |
| 3 | ArgumentLoopDetector | T | — | T | T | — | 3 same args |
| 4 | ToolErrorRateDetector | T | T | T | T | T | >30% error |
| 5 | SpecificToolErrorDetector | T | T | T | T | — | >30% per-tool |
| 6 | ToolLatencyDetector | — | T | — | T | — | 3.0x avg |
| 7 | ToolTimeoutDetector | — | T | — | T | T | >60s |
| 8 | RedundantToolCallDetector | — | — | — | T | — | ≥3 same output |
| 9 | CostSpikeDetector | T | T | T | T | T | $5 abs / 2x rel |
| 10 | CostVsBaselineDetector | — | T | — | — | T | 2x cohort avg |
| 11 | CostEfficiencyDetector | T | T | — | — | — | $0.50/tool or >20 calls |
| 12 | TokenExplosionDetector | — | — | T | T | — | 3x growth |
| 13 | PerToolCostSpikeDetector | — | T | — | — | — | 2x dominance |
| 14 | WastedToolCallsDetector | — | — | — | T | — | ≥3 same output |
| 15 | RunDurationDetector | — | T | — | — | T | 5x workload avg |
| 16 | MaxStepHitDetector | T | T | — | — | — | max_steps_hit |
| 17 | StepEfficiencyDetector | T | — | — | — | — | >20 calls success |
| 18 | InactivityDetector | — | — | T | — | — | >30s gap |
| 19 | PrematureCompletionDetector | T | — | — | — | — | error w/ <2 steps |
| 20 | RetryStormDetector | T | T | T | T | T | 5 retries |
| 21 | SystemicRetryDetector | T | T | T | — | — | all fail |
| 22 | TransientRetryDetector | — | T | — | T | — | ≥3 transient success |
| 23 | CascadingRetryDetector | — | — | T | T | — | retry chain depth |
| 24 | RecoveryPathDetector | T | — | — | — | — | extra steps post-error |
| 25 | InterventionFrequencyDetector | — | — | T | — | — | ≥3 interventions |
| 26 | EscalationRateDetector | — | — | T | — | — | 2x intervention/tool |
| 27 | ApprovalLatencyDetector | — | — | T | — | — | >60s approval |
| 28 | InterventionRejectionDetector | — | — | T | — | — | ≥2 rejections |
| 29 | EmptyResponseDetector | — | — | — | T | — | no content |
| 30 | LowOutputDetector | — | — | — | T | — | <50 chars |
| 31 | IndeterminateDetector | T | T | T | T | T | unknown status |
| 32 | OutputDriftDetector | — | T | — | — | T | 3x baseline length |
| 33 | AnomalyClusterDetector | — | T | — | — | T | ≥3 types/window |
| 34 | RunFrequencyAnomalyDetector | — | T | — | — | T | 3x run freq |
| 35 | FirstRunHeuristicDetector | — | T | — | — | T | first v1 run |

**Legend:** T = trigger scenario exists, — = unlikely to be triggered naturally

## Test Scenarios Per Detector

### 1. Tool Execution (8 detectors)

### LoopDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Why it's a loop |
|---|---|---|---|---|
| L1 | Request Triage (seeded) | Missing account (`acc_404`) — `lookup_account` fails, agent retries search + lookup | warning | Same tool pair repeats |
| L2 | Request Triage (parameterized) | Bad KB query that keeps returning non-matches, triggers repeated `search_kb` | critical | 12+ consecutive identical calls |
| L3 | Research Crew | Researcher finds incomplete data, Analyst rejects, Researcher retries same search 6x | warning | Cross-agent loop |
| L4 | RAG Q&A | Embedding mismatch causes repeated identical retrievals, agent retries query 7x | warning | Retrieval loop |

### LoopDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Why it's NOT a loop |
|---|---|---|---|
| L5 | Request Triage (parameterized) | Normal password reset — `search_kb` then `lookup_account` then resolve | Different tools, no repetition |
| L6 | Request Triage (parameterized) | Tool alternation — `search_kb` → `lookup_account` → `search_kb` → `lookup_account` | Alternating, not consecutive |
| L7 | Request Triage (parameterized) | Polling tool `wait-for-deploy` called 8x from allowlist | In allowlist, suppressed |
| L8 | Research Crew | Researcher runs 4 different searches (different queries) | Different tool name via arg? Actually same tool name. If all `search_tool` with 4 calls and threshold=5 → no fire. |
| L9 | RAG Q&A | Normal single retrieval then answer | One tool call |

### RetryStormDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Why it's a storm |
|---|---|---|---|---|
| R1 | Request Triage (seeded) | Loop scenario also produces retries on failed lookups | warning | 5+ retries |
| R2 | Request Triage (parameterized) | All tools fail — account lookup fails 8x, all retries fail | critical | Systemic failure, 0% success rate |
| R3 | Research Crew | Analyst rejects Researcher output 6x, all retries return same bad data | critical | Systemic, 0% success |
| R4 | RAG Q&A | Hallucination check fails 5x, agent retries with different prompts | warning | 5 retries |

### RetryStormDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Why it's NOT a storm |
|---|---|---|---|
| R5 | Request Triage (parameterized) | Normal run with 2 retries on a transient network error, both succeed | Below threshold |
| R6 | Request Triage (parameterized) | 6 retries but 5 succeed (transient errors) → downgraded to info or suppressed | ≥50% success rate |
| R7 | Research Crew | 3 retries on a bad search, all succeed | Below threshold |
| R8 | RAG Q&A | 4 retries on LLM timeout, all succeed eventually | Below threshold |
| R9 | All workloads | Any run with 0 retries | Clean run |

### CostSpikeDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Why it's a spike |
|---|---|---|---|---|
| C1 | Request Triage (seeded) | High-cost open-ended scenario — deep KB search chain | critical | Exceeds absolute threshold ($5) |
| C2 | Request Triage (parameterized) | 20-turn KB exhaustive search with large tool costs | critical | 3x absolute threshold |
| C3 | Research Crew | Deep research chain — Researcher finds 10 sources, Analyst validates all, Writer synthesizes | warning | Relative spike vs baseline |
| C4 | RAG Q&A | Embedding exhaustive scan across 50 documents | warning | Absolute threshold |

### CostSpikeDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Why it's NOT a spike |
|---|---|---|---|
| C5 | Request Triage (seeded) | Normal reset password — 2 tool calls | Cost is trivial |
| C6 | Request Triage (parameterized) | Medium workload but still under absolute threshold | Below $5 |
| C7 | Research Crew | Baseline too sparse (<5 runs) → relative check skipped, cost under absolute | Sparse baseline protection |
| C8 | RAG Q&A | Normal single-doc retrieval + short answer | Trivial cost |

### PatternLoopDetector — Positive Cases (must fire)
> Threshold: `detector_pattern_loop_window = 4` (window for pattern detection)

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| PL1 | Request Triage (seeded) | search_kb → lookup → search_kb → lookup repeats 6x in a window | warning | Alternating pattern detected in window |
| PL2 | RAG Q&A | retrieve → rank → retrieve → rank → retrieve → rank across 12 spans | critical | 6-cycle alternating pattern |

### PatternLoopDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| PL3 | Request Triage (param) | Normal workflow: search → lookup → resolve → close | Unique tools, no repeating pattern |
| PL4 | RAG Q&A | retrieve → retrieve → retrieve (short window, 3 cycles only) | Below window size |

### ArgumentLoopDetector — Positive Cases (must fire)
> Threshold: `detector_argument_loop_threshold = 3`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| AL1 | Request Triage (seeded) | search_kb("password reset") called 4x with identical args | warning | Same tool + same args repeated |
| AL2 | Research Crew | Researcher calls search("market trends 2025") 5x | critical | 5 identical arg repetitions |

### ArgumentLoopDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| AL3 | Request Triage (param) | search_kb("password") then search_kb("account") then search_kb("billing") | Same tool, different args |
| AL4 | RAG Q&A | retrieve("weather") called 2x then stop | Below threshold |

### ToolErrorRateDetector — Positive Cases (must fire)
> Threshold: `detector_tool_error_rate_pct = 30.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| TE1 | Request Triage (param) | 4 of 10 tool calls fail (40% error rate) | warning | 10 execute_tool spans, 4 with status=error |
| TE2 | Research Crew | 6 of 12 tool calls fail (50% error rate) | critical | Researcher + Analyst tools failing |

### ToolErrorRateDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| TE3 | Request Triage (seeded) | 1 of 10 tool calls fails (10% error rate) | Below 30% threshold |
| TE4 | RAG Q&A | 0 errors in 8 tool calls | Clean run |

### SpecificToolErrorDetector — Positive Cases (must fire)
> Threshold: `detector_specific_tool_error_pct = 30.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| SE1 | Request Triage (param) | search_kb called 5x, 2 fail (40%); lookup called 3x, all ok | warning | Single tool type exceeds error rate |
| SE2 | Research Crew | Researcher's search tool fails 3 of 5 calls (60%) | critical | Per-tool rate flag |

### SpecificToolErrorDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| SE3 | Request Triage (seeded) | search_kb 0/5 fail, lookup 1/5 fail (20%) | Both under threshold |
| SE4 | RAG Q&A | retrieve 1/8 fail (12.5%) | Below 30% |

### ToolLatencyDetector — Positive Cases (must fire)
> Threshold: `detector_tool_latency_multiplier = 3.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| TL1 | Request Triage (param) | search_kb avg 100ms; one lookup call takes 500ms (5x avg) | warning | Single outlier |
| TL2 | RAG Q&A | retrieve avg 200ms; one retrieval takes 1200ms (6x avg) | critical | Severe outlier |

### ToolLatencyDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| TL3 | Request Triage (param) | All tool calls 80-120ms (tight cluster) | No outliers |
| TL4 | RAG Q&A | Tool calls 100ms, 120ms (1.2x avg) | Under 3x multiplier |

### ToolTimeoutDetector — Positive Cases (must fire)
> Threshold: `detector_tool_timeout_seconds = 60.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| TT1 | Request Triage (param) | lookup_account takes 90s before failing | warning | >60s duration on one tool |
| TT2 | RAG Q&A | retrieve across 50 documents takes 180s | critical | 3x threshold |

### ToolTimeoutDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| TT3 | OSS fleet (Aider) | Tool calls all under 30s | Normal timing |
| TT4 | RAG Q&A | Standard retrieval under 10s | Fast execution |

### RedundantToolCallDetector — Positive Cases (must fire)
> Threshold: `detector_redundant_tool_threshold = 3`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| RC1 | RAG Q&A | retrieve called 4x returning same document | warning | 4 identical results |
| RC2 | RAG Q&A | search called 5x, all return empty "no results" | critical | 5 identical empty outputs |

### RedundantToolCallDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| RC3 | RAG Q&A | retrieve called 2x, different documents | Only 2 calls |
| RC4 | RAG Q&A | retrieve called 3x, 3 different docs | Different outputs

### 2. Cost & Resource (5 more detectors — CostSpikeDetector covered above)

### CostVsBaselineDetector — Positive Cases (must fire)
> Threshold: `detector_cost_vs_baseline_multiplier = 2.0`, `detector_cost_min_baseline_runs = 5`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| CV1 | Request Triage (param) | Cohort baseline $2.50; run costs $6.00 (2.4x) | warning | 2.4x > 2.0x threshold |
| CV2 | OSS fleet (Aider) | Cohort avg $0.80; heavy refactor run costs $3.20 (4x) | critical | 4x baseline |

### CostVsBaselineDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| CV3 | Request Triage (param) | Cohort baseline $2.50; run costs $3.00 (1.2x) | Under 2x multiplier |
| CV4 | Request Triage (param) | Cohort has <5 baseline runs | Sparse baseline, skipped |

### CostEfficiencyDetector — Positive Cases (must fire)
> Threshold: `detector_cost_per_tool_high = 0.50`, `detector_cost_efficiency_max_calls = 20`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| CE1 | Request Triage (param) | $8.00 cost for 10 tool calls ($0.80/tool) | warning | Per-tool > $0.50 |
| CE2 | Request Triage (seeded) | Successful run with 25 tool calls, $2.00 total | warning | >20 calls on success |

### CostEfficiencyDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| CE3 | Request Triage (param) | $4.00 for 15 tool calls ($0.27/tool) | Per-tool under threshold, calls under 20 |
| CE4 | Request Triage (param) | Failed run with 30 tool calls | Failed status, skipped |

### TokenExplosionDetector — Positive Cases (must fire)
> Threshold: `detector_token_explosion_multiplier = 3.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| TK1 | Research Crew | Early steps use 100 tokens; late Writer steps use 500 tokens (5x) | warning | 5x growth > 3x threshold |
| TK2 | RAG Q&A | Early: 50 token retrievals; late: full-doc synthesis at 400 tokens (8x) | critical | 8x growth |

### TokenExplosionDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| TK3 | RAG Q&A | All spans ~200 tokens | Flat token distribution |
| TK4 | Research Crew | Fewer than 4 spans total | Below minimum span count |

### PerToolCostSpikeDetector — Positive Cases (must fire)
> Threshold: `detector_per_tool_cost_multiplier = 2.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| PT1 | Request Triage (param) | search_kb is 6/8 tool calls (75% share, 3x dominance) | warning | One tool dominates call share |
| PT2 | Request Triage (param) | lookup_account is 8/10 calls (80% share, 4x dominance) | critical | Severe single-tool concentration |

### PerToolCostSpikeDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| PT3 | Request Triage (param) | 3 tools each ~33% share | Balanced distribution |
| PT4 | Request Triage (param) | Dominant tool has only 2 calls | Below minimum call count |

### WastedToolCallsDetector — Positive Cases (must fire)
> Threshold: `detector_wasted_tool_threshold = 3`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| WC1 | RAG Q&A | retrieve returns same doc string 4x | warning | 4 identical outputs |
| WC2 | RAG Q&A | search returns empty result 3x | warning | 3 identical empty outputs |

### WastedToolCallsDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| WC3 | RAG Q&A | retrieve returns 3 different docs | Unique outputs |
| WC4 | RAG Q&A | Only 2 tool calls total | Below threshold

### 3. Runtime & Completion (5 detectors)

### RunDurationDetector — Positive Cases (must fire)
> Threshold: `detector_run_duration_multiplier = 5.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| RD1 | Request Triage (param) | Workload avg 10s; run takes 65s (6.5x) | warning | >5x workload average |
| RD2 | OSS fleet | Workload avg 8s; browser-use run takes 90s (11x) | critical | 11x workload average |

### RunDurationDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| RD3 | Request Triage (param) | Workload avg 10s; run takes 25s (2.5x) | Under 5x multiplier |
| RD4 | RAG Q&A | Workload avg 5s; run takes 4s | Under average, clean |

### MaxStepHitDetector — Positive Cases (must fire)
> Threshold: max_steps_hit status

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| MS1 | Request Triage (seeded) | Agent runs 95 steps, hits configured max, status=max_steps_hit | warning | `total_tool_calls=51`, status=max_steps_hit |
| MS2 | Request Triage (param) | Agent loops close to max, hits 100-step limit | critical | 100 steps, max hit |

### MaxStepHitDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| MS3 | Request Triage (seeded) | Agent completes in 10 steps | Normal status |
| MS4 | RAG Q&A | 3-step retrieval + answer | Short run |

### StepEfficiencyDetector — Positive Cases (must fire)
> Threshold: `detector_step_efficiency_max_calls = 20`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| SF1 | Request Triage (param) | Successful run with 25 tool calls | warning | >20 calls on success |
| SF2 | Request Triage (param) | Successful run with 50 tool calls | critical | 50 > 20, 2.5x threshold |

### StepEfficiencyDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| SF3 | Request Triage (param) | Successful run with 8 tool calls | Well under 20 |
| SF4 | Request Triage (param) | 25 tool calls but status=failed | Only fires on success |

### InactivityDetector — Positive Cases (must fire)
> Threshold: `detector_inactivity_gap_seconds = 30.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| IA1 | Research Crew | Researcher pauses 45s before Analyst starts | warning | 45s gap > 30s |
| IA2 | Research Crew | 90s gap waiting for Writer approval | critical | 90s gap, 3x threshold |

### InactivityDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| IA3 | RAG Q&A | Steps 2-5s apart | No gaps |
| IA4 | Research Crew | 15s gap between Researcher and Analyst | Under 30s |

### PrematureCompletionDetector — Positive Cases (must fire)
> Threshold: < 2 steps on error/failure status

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| PC1 | Request Triage (seeded) | Agent errors after 1 tool call (status=error) | warning | error + only 1 span |
| PC2 | Request Triage (param) | Agent fails before invoking any tools, status=error | warning | error + just a root span |

### PrematureCompletionDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| PC3 | RAG Q&A | Agent completes normally in 3 steps, status=success | Normal completion |
| PC4 | Request Triage (param) | Agent errors after 5 tool calls | Triggers error rate, not premature |

### 4. Retry & Recovery (4 more detectors — RetryStormDetector covered above)

### SystemicRetryDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| SR1 | Request Triage (param) | 5 retries, all fail (0% success) | critical | Systemic failure pattern |
| SR2 | Research Crew | Analyst rejects Researcher output 6x, 0 success | critical | Cross-agent systemic failure |

### SystemicRetryDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| SR3 | Request Triage (param) | 5 retries, 4 succeed (80% success) | Not systemic |
| SR4 | RAG Q&A | 0 retries | No retries at all |

### TransientRetryDetector — Positive Cases (must fire)
> Threshold: `detector_transient_retry_threshold = 3`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| TR1 | Request Triage (param) | 3 temporary network errors, all retry and succeed | warning | 3 successful retries |
| TR2 | RAG Q&A | 5 LLM timeout retries, all eventually succeed | warning | 5 retries, all succeed |

### TransientRetryDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| TR3 | Request Triage (param) | 2 retries, both succeed | Below threshold |
| TR4 | RAG Q&A | 3 retries, all fail | Failed retries (systemic, not transient) |

### CascadingRetryDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| CR1 | Research Crew | Researcher→retry1→retry2→retry3, all failed downstream | warning | Retry chain depth 4 |
| CR2 | RAG Q&A | retrieve→retry1→retry2→retry3→retry4, deep cascade | critical | Deep retry chain |

### CascadingRetryDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| CR3 | Request Triage (param) | 1 retry, immediate success | Shallow retry chain |
| CR4 | RAG Q&A | Parallel 4 retrievals (not cascading) | Not a chain |

### RecoveryPathDetector — Positive Cases (must fire)
> Threshold: `detector_recovery_path_threshold = 5`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| RP1 | Request Triage (seeded) | 3 error tool calls + 7 recovery steps | warning | High error-to-success ratio |
| RP2 | Request Triage (param) | 6 errors + 10 recovery steps | critical | Deep recovery path |

### RecoveryPathDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| RP3 | Request Triage (param) | 1 error + 1 recovery step | Minimal recovery |
| RP4 | RAG Q&A | 0 errors | No recovery needed |

### 5. Interaction & Control (4 detectors)

### InterventionFrequencyDetector — Positive Cases (must fire)
> Threshold: `detector_intervention_frequency_threshold = 3`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| IF1 | Research Crew | Analyst asks for human confirmation 4x | warning | 4 human_intervention spans |
| IF2 | Research Crew | 3 interventions in a 3-agent crew (Researcher, Analyst, Writer each ask) | warning | 3 interventions |

### InterventionFrequencyDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| IF3 | Request Triage (param) | Fully automated, 0 interventions | No interventions |
| IF4 | Research Crew | 2 requests for confirmation | Below threshold |

### EscalationRateDetector — Positive Cases (must fire)
> Threshold: `detector_escalation_rate_multiplier = 2.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| ER1 | Research Crew | 3 interventions / 5 tool calls (60% ratio) | warning | Intervention-to-tool ratio > 2x normal |
| ER2 | Research Crew | 4 interventions / 5 tool calls (80% ratio) | critical | Very high escalation rate |

### EscalationRateDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| ER3 | Research Crew | 1 intervention / 20 tool calls (5% ratio) | Low escalation |
| ER4 | Request Triage (param) | 0 interventions | No escalations |

### ApprovalLatencyDetector — Positive Cases (must fire)
> Threshold: `detector_approval_latency_seconds = 60.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| AP1 | Research Crew | await_approval span takes 90s | warning | >60s approval wait |
| AP2 | Research Crew | await_approval span takes 200s | critical | >3x threshold |

### ApprovalLatencyDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| AP3 | Research Crew | await_approval span takes 15s | Fast approval |
| AP4 | Request Triage (param) | No await_approval spans | No approval needed |

### InterventionRejectionDetector — Positive Cases (must fire)
> Threshold: `detector_intervention_rejection_threshold = 2`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| IR1 | Research Crew | 2 human interventions, both rejected | warning | 2 rejections |
| IR2 | Research Crew | 3 interventions, all rejected | critical | 3 rejections, systemic |

### InterventionRejectionDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| IR3 | Research Crew | 2 interventions, both accepted | No rejections |
| IR4 | Request Triage (param) | No human intervention spans | No interaction |

### 6. Output Quality (4 detectors)

### EmptyResponseDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| EM1 | RAG Q&A | Agent returns empty string as final response | warning | No gen_ai.response.content |
| EM2 | RAG Q&A | Agent errors mid-response, produces no output | warning | Output missing entirely |

### EmptyResponseDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| EM3 | RAG Q&A | Normal 200-char answer | Non-empty response |
| EM4 | Request Triage (param) | Tool-only run with generated report | Content present |

### LowOutputDetector — Positive Cases (must fire)
> Threshold: `detector_low_output_min_chars = 50`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| LO1 | RAG Q&A | Response contains 20 characters ("Answer: yes") | warning | <50 chars |
| LO2 | RAG Q&A | Response contains 10 characters ("OK.") | warning | Very short output |

### LowOutputDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| LO3 | RAG Q&A | Response 200 characters | Above 50 char threshold |
| LO4 | Research Crew | Writer produces a 2000-word report | Long output |

### IndeterminateDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| ID1 | Request Triage (param) | Run completes with status=unknown | warning | No clear pass/fail |
| ID2 | RAG Q&A | Agent exits with status=None (timeout) | warning | Missing status |

### IndeterminateDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| ID3 | Request Triage (param) | Run completes with status=success | Clear status |
| ID4 | RAG Q&A | Run exits with status=error | Clear (though error) status |

### OutputDriftDetector — Positive Cases (must fire)
> Threshold: `detector_output_drift_multiplier = 3.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| OD1 | Request Triage (param) | Baseline avg output 100 chars; run output 350 chars | warning | 3.5x > 3x threshold |
| OD2 | OSS fleet | Baseline avg 200 chars; run produces 1200 chars | critical | 6x deviation |

### OutputDriftDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| OD3 | Request Triage (param) | Baseline 100 chars; run 150 chars (1.5x) | Under 3x |
| OD4 | Request Triage (param) | Baseline <5 runs | Sparse baseline, skipped |

### 7. Cross-Run Patterns (3 detectors)

### AnomalyClusterDetector — Positive Cases (must fire)
> Threshold: `detector_anomaly_cluster_min_types = 3`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| AC1 | Request Triage (param) | Run triggers loop + retry_storm + cost_spike (3 types) | warning | 3 anomaly types in one run |
| AC2 | OSS fleet | Run triggers loop + tool_error_rate + token_explosion + empty_response | warning | 4 anomaly types |

### AnomalyClusterDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| AC3 | Request Triage (param) | Run triggers only 2 anomaly types | Below 3-type threshold |
| AC4 | OSS fleet | Clean run, 0 anomalies | No anomalies at all |

### RunFrequencyAnomalyDetector — Positive Cases (must fire)
> Threshold: `detector_run_frequency_min_runs = 5`, `detector_run_frequency_max_multiplier = 3.0`

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| RF1 | Request Triage (param) | Cohort average 5 runs/hour; this agent generates 20 runs | warning | 4x > 3x frequency |
| RF2 | OSS fleet | Cohort avg 3 runs/hour; agent generates 15 runs (5x) | critical | 5x frequency |

### RunFrequencyAnomalyDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| RF3 | Request Triage (param) | Cohort avg 5 runs; agent at 8 (1.6x) | Under 3x |
| RF4 | OSS fleet | Cohort has <5 baseline runs | Sparse baseline, skipped |

### FirstRunHeuristicDetector — Positive Cases (must fire)

| # | Workload | Scenario | Expected severity | Trace shape |
|---|---|---|---|---|
| FH1 | Request Triage (param) | First run of agent version v2; v1 has 10 prior runs | warning | Previous version exists, first v2 run |
| FH2 | OSS fleet | Aider bumped from v1.0 to v1.1; first v1.1 run | warning | Version cohort transition |

### FirstRunHeuristicDetector — Negative Cases (must NOT fire)

| # | Workload | Scenario | Trace shape |
|---|---|---|---|
| FH3 | Request Triage (param) | Agent v1, run# 25 of this version | Not a first run |
| FH4 | Request Triage (param) | Agent v2 first run, but v1 has 0 baseline runs | No previous version cohort

## Recipe Appendix — Hard-to-Trigger Detectors

Detectors that require cohorts, cross-run state, or timed interactions need explicit
trace-construction recipes. These are used by the seeding scripts in 8.9.2 and the
150K-trace validation run in 8.8.3.

### CostVsBaselineDetector

**Requires:** A version cohort with ≥5 prior runs and a baseline cost average.

**Positive recipe:**
1. Create 5 prior runs for agent `triage` version `v1`, each with `estimated_cost=$2.50`.
2. Run the detector on a 6th run with `estimated_cost=$6.00`.
3. Expected: `cost_vs_baseline` anomaly fires (2.4x > 2.0x multiplier), severity=warning.

**Negative recipe:**
1. Same 5 prior runs at $2.50 avg. Run detector on a 6th run at $3.00.
2. Expected: no anomaly (1.2x < 2.0x multiplier).
3. Also test: only 3 prior runs. Expected: skipped (below min_baseline_runs=5).

### AnomalyClusterDetector

**Requires:** A single run triggering ≥3 distinct anomaly types.

**Positive recipe:**
1. Construct a trace with spans that trigger all three simultaneously: a tool called 5x
   consecutively (loop), 5 retries in the summary (retry_storm), and `estimated_cost=$6.00`
   (cost_spike). Run the full detector pipeline.
2. Expected: `anomaly_cluster` anomaly fires with 3+ contributing types.

**Negative recipe:**
1. Trigger only loop + cost_spike (2 types).
2. Expected: no cluster anomaly.

### RunFrequencyAnomalyDetector

**Requires:** A version cohort baseline for run frequency (runs/hour).

**Positive recipe:**
1. Agent `triage` v1 averages 5 runs/hour over a window. The current run is the 20th in
   the window (~20 runs/hour, 4x the baseline).
2. Expected: `run_frequency_anomaly` fires, severity depends on ratio.

**Negative recipe:**
1. Same baseline (5 runs/hour), only 8 runs this hour (1.6x).
2. Expected: skipped.
3. Also: <5 baseline runs. Expected: skipped (below min_runs).

### FirstRunHeuristicDetector

**Requires:** A version cohort where the previous version has runs but the new one does not.

**Positive recipe:**
1. Agent `triage` v1 has 10 prior runs. Submit the first run of v2.
2. Expected: `first_run_heuristic` fires, severity=warning.

**Negative recipe:**
1. Agent `triage` v1 has 10 prior runs. Submit the 25th run of v1 (not first).
2. Expected: no anomaly.
3. Also: v2 first run but v1 has 0 prior runs. Expected: skipped (no previous cohort).

### OutputDriftDetector

**Requires:** A version cohort baseline for average output length.

**Positive recipe:**
1. 5 prior runs of agent `triage` v1 average 100 characters of output. Submit a run
   with 350 characters (`gen_ai.response.content`).
2. Expected: `output_drift` fires (3.5x > 3.0x multiplier), severity=warning.

**Negative recipe:**
1. Same baseline, 150-char run. Expected: no anomaly (1.5x, under threshold).
2. Also: only 3 prior baseline runs. Expected: skipped.

### ApprovalLatencyDetector

**Requires:** A human interaction span (await_approval) with a timed duration.

**Positive recipe:**
1. Add `SpanNode(operation_name="await_approval", duration_ms=90000)` to the span tree.
2. Expected: `approval_latency` fires (90s > 60s threshold).

**Negative recipe:**
1. `await_approval` at 15s. Expected: no anomaly.
2. No `await_approval` span at all. Expected: no anomaly.

### InterventionRejectionDetector

**Requires:** Multiple human_intervention spans, some marked as rejected.

**Positive recipe:**
1. Span tree: `human_intervention(...)` → `human_intervention(...)` (2 spans,
   both with attributes indicating rejection).
2. Expected: `intervention_rejection` fires (2 ≥ threshold=2).

**Negative recipe:**
1. 2 interventions, both accepted. Expected: no anomaly.
2. Only 1 intervention. Expected: below threshold.

### EscalationRateDetector

**Requires:** Both interventions and tool calls in the same run.

**Positive recipe:**
1. Summary with `total_interventions=3` and `total_tool_calls=5` (ratio 60%).
2. Expected: `escalation_rate` fires (ratio exceeds 2x normal escalation).

**Negative recipe:**
1. `total_interventions=1`, `total_tool_calls=20` (ratio 5%). Expected: no anomaly.
2. `total_interventions=0`. Expected: no anomaly (no escalation).

## Execution Timeline (~2 hours)

### Phase 1: Setup & Calibration (15 min)

| Step | Duration | Activity |
|---|---|---|
| 1.1 | 2 min | Start docker compose stack (Jaeger, Postgres, collector, API, web app) |
| 1.2 | 5 min | Run all 3 seeded Request Triage scenarios (normal, loop, high_cost), verify traces in Jaeger |
| 1.3 | 3 min | Run analytics worker, verify summaries materialized, verify 2 anomalies detected (loop + cost spike), verify 0 false positives on normal run |
| 1.4 | 5 min | Set up CrewAI Research Crew + RAG Q&A + instrument 15 OSS agents |

### Phase 2: Bulk Run (75 min)

| Step | Duration | Activity |
|---|---|---|
| 2.1 | 15 min | Run Request Triage parameterized batch: 10 randomized input sets, 4 runs each. Total: 40 runs. Establishes baseline cohort for cross-run detectors. |
| 2.2 | 15 min | Run Research Crew: 3 variants (shallow, deep, conflict research). 10 runs each. Total: 30 runs. Triggers interaction/approval/retry-cascade scenarios. |
| 2.3 | 15 min | Run RAG Q&A: 3 variants (simple, ambiguous, hallucination-prone). 10 runs each. Total: 30 runs. Triggers output quality, redundant call, wasted call scenarios. |
| 2.4 | 25 min | Run 15 OSS agent fleet (LangGraph, CrewAI, AutoGen, browser-use, aider, SuperAGI, OpenAI Agents, etc.) — 6 runs each. Total: ~90 runs. Validates cross-framework detection. |
| 2.5 | 5 min | Let analytics worker catch up, verify all runs ingested, materialize fleet rollups + version cohorts, run cross-run detectors |

### Phase 3: Review & Verdict (30 min)

| Step | Duration | Activity |
|---|---|---|
| 3.1 | 10 min | Open anomaly inbox in web UI. For each anomaly, classify TP/FP/FN on the 35-detector review sheet. Complete all 7 category sections. |
| 3.2 | 10 min | Score clarity (1-5) and actionability (1-5) for each anomaly. Cross-check recipe-appendix detectors for expected outcomes. Note any false negatives. |
| 3.3 | 10 min | Compute per-detector TPR/FPR, overall metrics table. Fill expected TP/FP/FN per-detector tracking. Write verdict paragraph. |

## Review Protocol

For every anomaly that fires, record:

```
Anomaly ID | Run ID | Agent | Detector | TP/FP | Clarity (1-5) | Actionability (1-5) | Notes
```

**TP (True Positive):** The anomaly correctly identifies a real problem.
**FP (False Positive):** The anomaly fired but there is no real problem.
**FN (False Negative):** A seeded failure scenario ran but no anomaly fired.

## Validation Criteria (STRICT)

The field test passes ONLY if ALL of the following are met. Any single failure is a FAIL.

### Per-Detector Metrics (all 35 detectors)

| Metric | All 35 Detectors |
|---|---|
| **True Positive Rate** | ≥ 95% per detector |
| **False Positive Rate** | ≤ 5% per detector |
| **Zero FPs on known-normal runs** | Required for all |
| **All seeded positive scenarios fire** | Required for all |

### Severity Accuracy

| Requirement | Threshold |
|---|---|
| Correct severity assigned (warning vs critical) | 100% of anomalies |
| No critical downgrades for known-critical scenarios | Required |
| No warning upgrades for known-warning scenarios | Required |

### Operator Experience

| Metric | Threshold |
|---|---|
| Average clarity score | ≥ 4.5 / 5 |
| Average actionability score | ≥ 4.5 / 5 |
| No anomaly with clarity < 3 | Required |
| No anomaly with actionability < 3 | Required |

### Cross-Workload Consistency

| Requirement | Threshold |
|---|---|
| Same failure pattern caught across LangGraph and CrewAI | Required |
| Same failure pattern caught across 15-OSS-agent fleet | Required |
| No framework-specific false positives | Required |
| Polling allowlist correctly suppresses known-polling tools | Required |

### Cross-Run / Baseline Coverage

| Requirement | Threshold |
|---|---|
| CostVsBaseline fires with ≥5 baseline runs | Required |
| OutputDrift fires with sufficient baseline | Required |
| AnomalyCluster fires with ≥3 anomaly types in one run | Required |
| RunFrequencyAnomaly fires with cohort comparison | Required |
| FirstRunHeuristic fires on version transition | Required |

### False Negative Audit

| Requirement | Threshold |
|---|---|
| All 70+ positive scenarios fire (across all 35 detectors) | 100% |
| Any missed seeded failure | **Immediate FAIL** |

## Anomaly Review Sheet (to fill during test)

Each detector gets a mini-sheet. Fill during Phase 3 review. **TP** = True Positive,
**FP** = False Positive, **FN** = False Negative (seeded failure missed).

```
=== TOOL EXECUTION (8) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
LoopDetector           | L1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | L2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | L3 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | L4 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | L5 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | L6 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | L7 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
PatternLoopDetector    | PL1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | PL2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
ArgumentLoopDetector   | AL1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | AL2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
ToolErrorRateDetector  | TE1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | TE2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
SpecificToolErrorDet   | SE1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | SE2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
ToolLatencyDetector    | TL1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | TL2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
ToolTimeoutDetector    | TT1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | TT2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
RedundantToolCallDet   | RC1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | RC2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other tool anomalies? List:

=== COST & RESOURCE (6) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
CostSpikeDetector      | C1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | C2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | C3 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | C4 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | C7 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
CostVsBaselineDetector | CV1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | CV2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
CostEfficiencyDetector | CE1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | CE2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
TokenExplosionDetector | TK1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | TK2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
PerToolCostSpikeDet    | PT1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | PT2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
WastedToolCallsDet     | WC1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | WC2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other cost anomalies? List:

=== RUNTIME & COMPLETION (5) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
RunDurationDetector    | RD1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | RD2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
MaxStepHitDetector     | MS1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | MS2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
StepEfficiencyDetector | SF1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | SF2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
InactivityDetector     | IA1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | IA2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
PrematureCompletionDet | PC1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | PC2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other runtime anomalies? List:

=== RETRY & RECOVERY (5) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
RetryStormDetector     | R1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | R2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | R3 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | R4 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | R6 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
SystemicRetryDetector  | SR1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | SR2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
TransientRetryDetector | TR1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | TR2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
CascadingRetryDetector | CR1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | CR2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
RecoveryPathDetector   | RP1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | RP2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other retry anomalies? List:

=== INTERACTION & CONTROL (4) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
InterventionFreqDet    | IF1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | IF2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
EscalationRateDetector | ER1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | ER2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
ApprovalLatencyDet     | AP1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | AP2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
InterventionRejectDet  | IR1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | IR2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other interaction anomalies? List:

=== OUTPUT QUALITY (4) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
EmptyResponseDetector  | EM1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | EM2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
LowOutputDetector      | LO1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | LO2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
IndeterminateDetector  | ID1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | ID2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
OutputDriftDetector    | OD1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | OD2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other output anomalies? List:

=== CROSS-RUN PATTERNS (3) ===
Detector | Scenario ID | Run ID | Fired? | TP/FP/FN | Severity ok? | Clarity | Actionability | Notes
AnomalyClusterDetector | AC1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | AC2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
RunFrequencyAnomalyDet | RF1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | RF2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
FirstRunHeuristicDet   | FH1 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
                       | FH2 | ___ | Y/N | TP/FP/FN | Y/N | __/5 | __/5 |
Any other cross-run anomalies? List:

=== FALSE NEGATIVE AUDIT ===
Seeded scenario that should have fired but did NOT:
- (none expected)

=== EXPECTED TP / FP / FN PER DETECTOR ===
Detector     | Expected TP | Expected FP | Expected FN
LoopDetector | L1-L4       | L5-L7       | 0
PatternLoop  | PL1-PL2     | PL3-PL4     | 0
ArgumentLoop | AL1-AL2     | AL3-AL4     | 0
ToolErrorRate| TE1-TE2     | TE3-TE4     | 0
SpecificToolErr| SE1-SE2   | SE3-SE4     | 0
ToolLatency  | TL1-TL2     | TL3-TL4     | 0
ToolTimeout  | TT1-TT2     | TT3-TT4     | 0
RedundantTool| RC1-RC2     | RC3-RC4     | 0
CostSpike    | C1-C4       | C5-C8       | 0
CostVsBaseline| CV1-CV2    | CV3-CV4     | 0
CostEfficiency| CE1-CE2    | CE3-CE4     | 0
TokenExplosion| TK1-TK2    | TK3-TK4     | 0
PerToolCostSpike| PT1-PT2  | PT3-PT4     | 0
WastedToolCalls| WC1-WC2   | WC3-WC4     | 0
RunDuration  | RD1-RD2     | RD3-RD4     | 0
MaxStepHit   | MS1-MS2     | MS3-MS4     | 0
StepEfficiency| SF1-SF2    | SF3-SF4     | 0
Inactivity   | IA1-IA2     | IA3-IA4     | 0
PrematureCompletion| PC1-PC2| PC3-PC4    | 0
RetryStorm   | R1-R4       | R5-R9       | 0
SystemicRetry| SR1-SR2     | SR3-SR4     | 0
TransientRetry| TR1-TR2    | TR3-TR4     | 0
CascadingRetry| CR1-CR2    | CR3-CR4     | 0
RecoveryPath | RP1-RP2     | RP3-RP4     | 0
InterventionFreq| IF1-IF2  | IF3-IF4     | 0
EscalationRate| ER1-ER2    | ER3-ER4     | 0
ApprovalLatency| AP1-AP2   | AP3-AP4     | 0
InterventionReject| IR1-IR2| IR3-IR4     | 0
EmptyResponse| EM1-EM2     | EM3-EM4     | 0
LowOutput    | LO1-LO2     | LO3-LO4     | 0
Indeterminate| ID1-ID2     | ID3-ID4     | 0
OutputDrift  | OD1-OD2     | OD3-OD4     | 0
AnomalyCluster| AC1-AC2    | AC3-AC4     | 0
RunFrequencyAnomaly| RF1-RF2| RF3-RF4    | 0
FirstRunHeuristic| FH1-FH2  | FH3-FH4     | 0

=== OVERALL METRICS ===
(TPR = True Positive Rate, FPR = False Positive Rate)

Tool Execution (8 detectors):
  LoopDetector:       TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  PatternLoopDet:     TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  ArgumentLoopDet:    TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  ToolErrorRateDet:   TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  SpecificToolErrDet: TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  ToolLatencyDet:     TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  ToolTimeoutDet:     TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  RedundantToolCall:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

Cost & Resource (6 detectors):
  CostSpikeDet:       TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  CostVsBaselineDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  CostEfficiencyDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  TokenExplosionDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  PerToolCostSpike:   TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  WastedToolCalls:    TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

Runtime & Completion (5 detectors):
  RunDurationDet:     TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  MaxStepHitDet:      TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  StepEfficiencyDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  InactivityDet:      TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  PrematureCompletion: TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

Retry & Recovery (5 detectors):
  RetryStormDet:      TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  SystemicRetryDet:   TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  TransientRetryDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  CascadingRetryDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  RecoveryPathDet:    TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

Interaction & Control (4 detectors):
  InterventionFreq:   TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  EscalationRateDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  ApprovalLatencyDet: TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  InterventionReject: TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

Output Quality (4 detectors):
  EmptyResponseDet:   TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  LowOutputDet:       TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  IndeterminateDet:   TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  OutputDriftDet:     TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

Cross-Run Patterns (3 detectors):
  AnomalyClusterDet:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  RunFrequencyDet:    TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5
  FirstRunHeuristic:  TPR=__%  FPR=__%  Clarity=__/5  Actionability=__/5

=== VERDICT ===
PASS / FAIL

Reason:
```

## Post-Field-Test Deliverables

1. Completed 35-detector anomaly review sheet with all metrics and TP/FP/FN tracking
2. Per-detector threshold adjustment recommendations (all 35)
3. List of any false positives with root cause analysis
4. List of any false negatives with root cause analysis
5. Cross-framework validation report (LangGraph, CrewAI, AutoGen, browser-use, aider, SuperAGI, OpenAI Agents)
6. Cross-run / baseline validation report (CostVsBaseline, OutputDrift, AnomalyCluster, RunFrequency)
7. Go/no-go recommendation for v1.0 production readiness
8. If FAIL: specific list of blockers and required fixes

## WBS Integration

This field test maps to:

- **WBS 6.6**: Field-test handoff requirement — this document IS the handoff
- **WBS 6.7**: Anomaly validation matrix — the 35-detector scenario tables above ARE the expanded matrix
- **WBS 8.6.5**: (#95) Updated field-test plan with 35-detector scenarios — this document
- **WBS 8.8.3**: (#83) Run 35 detectors against 150K traces — recipe appendix provides seed recipes
- **WBS 8.9**: Field-Test Execution milestone — this plan drives 8.9.2 (run scenarios), 8.9.4 (run detectors), and 8.9.5 (produce report)
- **Milestone 12**: Release validation — the field test report IS the release gate evidence
