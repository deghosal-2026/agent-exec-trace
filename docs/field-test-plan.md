# Field-Test Plan — Anomaly Detection v0.1.0

Anomaly detection in v0.1.0 is seeded and deterministic. This field test gates production
confidence for v1.0 by validating detectors against multiple frameworks, workloads, and failure
modes under strict metrics.

## Pre-Flight: Detector Hardening

Before field test execution, harden the three detectors against known blind spots:

| Detector | Blind spot | Hardening |
|---|---|---|
| **LoopDetector** | False positives for intentional polling tools | Add `polling_tool_allowlist` config. Tools in the allowlist skip loop detection. |
| **RetryStormDetector** | No distinction between transient retries (succeeded) vs systemic (all failed) | Add `retry_success_rate` check. If ≥ 50% of retries ultimately succeeded, downgrade severity to `info` or suppress. |
| **CostSpikeDetector** | Sparse baseline (1-2 runs skews average) | Add `min_baseline_run_count` (default 5). Skip relative check if baseline cohort has fewer runs. |

## Agent Workloads

| # | Agent | Framework | Adapter | What it does | Runs |
|---|---|---|---|---|---|
| 1 | **Request Triage** (seeded) | LangGraph | TracedGraph | Classifies support requests, searches KB, looks up accounts | 15 |
| 2 | **Request Triage** (parameterized) | LangGraph | TracedGraph | Same agent with 10+ randomized input batches | 40 |
| 3 | **Research Crew** | CrewAI | @trace_agent | 3-agent crew: Researcher → Analyst → Writer | 30 |
| 4 | **RAG Q&A** | LangGraph | TracedGraph | Retrieval-augmented Q&A with hallucination retries | 30 |
| | | | | **Total** | **~115** |

## Test Scenarios Per Detector

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

## Execution Timeline (55 minutes)

### Phase 1: Setup & Calibration (10 min)

| Step | Duration | Activity |
|---|---|---|
| 1.1 | 2 min | Start docker compose stack (Jaeger, Postgres, collector, API, web app) |
| 1.2 | 3 min | Run all 3 seeded Request Triage scenarios (normal, loop, high_cost), verify traces in Jaeger |
| 1.3 | 3 min | Run analytics worker, verify summaries materialized, verify 2 anomalies detected (loop + cost spike), verify 0 false positives on normal run |
| 1.4 | 2 min | Set up CrewAI Research Crew script + instrumentation, set up RAG Q&A agent |

### Phase 2: Bulk Run (30 min)

| Step | Duration | Activity |
|---|---|---|
| 2.1 | 10 min | Run Request Triage parameterized batch: 10 randomized input sets, 4 runs each (varying account IDs, intents, KB queries). Total: 40 runs. |
| 2.2 | 10 min | Run Research Crew: 3 variants (shallow research, deep research, conflict research). 10 runs each. Total: 30 runs. |
| 2.3 | 8 min | Run RAG Q&A: 3 variants (simple query, ambiguous query, hallucination-prone query). 10 runs each. Total: 30 runs. |
| 2.4 | 2 min | Let analytics worker catch up, verify all runs ingested, materialize fleet rollups + version cohorts |

### Phase 3: Review & Verdict (15 min)

| Step | Duration | Activity |
|---|---|---|
| 3.1 | 5 min | Open anomaly inbox in web UI. For each anomaly, classify TP/FP on the review sheet. |
| 3.2 | 5 min | Score clarity (1-5) and actionability (1-5) for each anomaly. Note any false negatives (seeded failures that were missed). |
| 3.3 | 5 min | Compute metrics per detector. Write verdict paragraph. |

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

### Per-Detector Metrics

| Metric | LoopDetector | RetryStormDetector | CostSpikeDetector |
|---|---|---|---|
| **True Positive Rate** | ≥ 95% | ≥ 95% | ≥ 95% |
| **False Positive Rate** | ≤ 5% | ≤ 5% | ≤ 5% |
| **Zero FPs on known-normal** | Required | Required | Required |
| **All seeded failures caught** | Required | Required | Required |

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
| No framework-specific false positives | Required |
| Polling allowlist correctly suppresses known-polling tools | Required |

### False Negative Audit

| Requirement | Threshold |
|---|---|
| Seeded failures detected (all positive scenarios L1-L4, R1-R4, C1-C4) | 100% |
| Any missed seeded failure | **Immediate FAIL** |

## Anomaly Review Sheet (to fill during test)

```
=== LOOP DETECTOR ===
Scenario | Run ID | Fired? | TP/FP | Severity Correct? | Clarity | Actionability | Notes
L1 (seeded loop)       | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
L2 (parameterized loop)| ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
L3 (crew loop)         | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
L4 (rag loop)          | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
L5 (normal alt)        | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
L6 (alternating)       | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
L7 (polling allowlist) | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
Any other loop anomalies? List:

=== RETRY STORM DETECTOR ===
Scenario | Run ID | Fired? | TP/FP | Severity Correct? | Clarity | Actionability | Notes
R1 (seeded retries)     | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
R2 (systemic fail)      | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
R3 (crew retries)       | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
R4 (rag retries)        | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
R6 (transient ok)       | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
Any other retry storm anomalies? List:

=== COST SPIKE DETECTOR ===
Scenario | Run ID | Fired? | TP/FP | Severity Correct? | Clarity | Actionability | Notes
C1 (seeded high cost)   | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
C2 (parameterized cost) | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
C3 (crew cost)          | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
C4 (rag cost)           | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
C7 (sparse baseline)    | ___ | Yes/No | TP/FP | Yes/No | __/5 | __/5 |
Any other cost spike anomalies? List:

=== FALSE NEGATIVE AUDIT ===
Seeded scenario that should have fired but did NOT:
- (none expected)

=== OVERALL METRICS ===
LoopDetector:      TPR = __%  FPR = __%  Clarity = __/5  Actionability = __/5
RetryStormDetector: TPR = __%  FPR = __%  Clarity = __/5  Actionability = __/5
CostSpikeDetector:  TPR = __%  FPR = __%  Clarity = __/5  Actionability = __/5

=== VERDICT ===
PASS / FAIL

Reason:
```

## Post-Field-Test Deliverables

1. Completed anomaly review sheet with all metrics
2. Per-detector threshold adjustment recommendations
3. List of any false positives with root cause analysis
4. List of any false negatives with root cause analysis
5. Go/no-go recommendation for v1.0 production readiness
6. If FAIL: specific list of blockers and required fixes

## WBS Integration

This field test maps to:

- **WBS 6.6**: Field-test handoff requirement — this document IS the handoff
- **WBS 6.7**: Anomaly validation matrix — the scenario table above IS the expanded matrix
- **Milestone 12**: Release validation — the field test report IS the release gate evidence
