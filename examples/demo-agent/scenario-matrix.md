# request-triage Scenario Matrix — v0.1.0

> Maps every seeded run to its fixture, expected run outcome, the detector(s) it must
> exercise, and the UI surfaces it is expected to populate. Source of truth for demo,
> analytics, and replay work.

## Scenarios

| Scenario | Fixture | Seed | Expected outcome | Detectors exercised | UI views to populate |
|---|---|---|---|---|---|
| `normal` | `fixtures/normal.json` | `seeds.normal_request` | `resolve` / `ok`, <= 3 steps, low cost | none | Run Timeline (healthy), Fleet Health row |
| `loop` | `fixtures/loop.json` | `seeds.loop_request` | `escalate` / `error`, ~`MAX_STEPS` tool calls, repeated `search_kb` + `lookup_account` | **Loop detector** (attaches `loop.count`) | Run Timeline (loop markers), Anomaly Inbox |
| `high_cost` | `fixtures/high_cost.json` | `seeds.high_cost_request` | `escalate` / `error`, `MAX_STEPS` `search_kb` turns, elevated `estimated_cost` | **Cost detector** (cost-per-run spike) | Run Timeline, Fleet (cost), Anomaly Inbox |
| `retry` (future) | `fixtures/retry.json` | `seeds.retry_request` | planned for retry-storm detector | Retry detector | Anomaly Inbox |

## Expected run outcomes

Each seat should produce a run whose materialized summary matches these assertions
(used by the analytics integration tests later):

- **normal**: `status == "ok"`, `tool_call_count` small, `retry_count == 0`,
  `loop_detected == false`, `estimated_cost` at baseline.
- **loop**: `status == "error"`, high `retry_count`, repeated `execute_tool` sequences,
  `loop_detected == true`.
- **high_cost**: `status == "error"`, `estimated_cost` several multiples of the normal
  run baseline, no loop (tool calls are distinct), cost anomaly with explanation.

## Version-comparison note

Runs may be emitted with `agent_version` overrides so `version_cohort_summaries` can be
materialized for the Version Compare view. Provide at least two version labels
(e.g. `v0.1.0` and `v0.1.1`) when generating demo cohorts.

## Detector validation mapping

See WBS 6.7 for the full detector-by-scenario matrix (true positives and known
non-goals). The three seeded scenarios above are the minimum positive cases used to
return the view/detectors real before field testing.