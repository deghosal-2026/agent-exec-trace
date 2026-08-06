# Anomaly Validation Matrix — v0.1.0

## Detector: Loop

| Case | Expected Outcome | Notes |
|------|-----------------|-------|
| Same tool called 5x consecutively | Loop anomaly (warning) | Default threshold = 5 |
| Same tool called 10x consecutively | Loop anomaly (critical) | Severity escalation at >= 10 |
| Same tool called 4x consecutively | No anomaly | Below threshold |
| Different tools alternated | No anomaly | No consecutive repetition |
| One tool called 5x, then different tool | No anomaly | Not consecutive |
| No tool spans | No anomaly | Empty span tree |
| Tool called 5x across 5 different phases | No anomaly | Not consecutive |

### Known blind spots for v0.1.0

- **Polling tools**: An agent that intentionally polls (e.g. `wait-for-deploy` called 10x) will fire a false positive loop anomaly. No built-in allowlist mechanism.
- **Cross-phase repetition**: Repetition of the same tool across different planning phases (architecturally different) is not distinguished from same-phase repetition.
- **Argument-aware detection**: Only tool name is compared; different arguments to the same tool are not distinguished.

---

## Detector: Retry Storm

| Case | Expected Outcome | Notes |
|------|-----------------|-------|
| `total_retries = 5` | Retry storm anomaly (warning) | Default threshold = 5 |
| `total_retries = 10` | Retry storm anomaly (critical) | Severity escalation at >= 10 |
| `total_retries = 4` | No anomaly | Below threshold |
| `total_retries = 0` | No anomaly | Clean run |

### Known blind spots for v0.1.0

- **Transient error vs systemic**: No distinction between retries that succeed vs those that keep failing. A run with 5 retries that all succeed still fires.
- **Workload-aware thresholds**: Single threshold applied across all workloads. No per-workload threshold tuning.
- **No window-based detection**: A run with 3 retries in the first second and 2 more 10 minutes later counts the same as 5 consecutive retries.

---

## Detector: Cost Spike

| Case | Expected Outcome | Notes |
|------|-----------------|-------|
| `estimated_cost = 5.01` | Cost spike (absolute, warning) | Default threshold = 5.0 |
| `estimated_cost = 15.01` | Cost spike (absolute, critical) | 3x threshold → critical |
| `estimated_cost = 1.0, baseline = 0.40, multiplier = 2.0` | Cost spike (relative, warning) | 2.5x baseline exceeds 2.0x multiplier |
| `estimated_cost = 1.0, baseline = 0.60, multiplier = 2.0` | No anomaly | 1.67x is below 2.0x multiplier |
| `estimated_cost = 1.0, no baseline` | No anomaly | Below absolute threshold |
| `estimated_cost = None` | No anomaly | No cost data |
| `estimated_cost = 10.0, no baseline` | Cost spike (absolute, critical) | Only absolute check fires |

### Known blind spots for v0.1.0

- **Sparse baseline**: If a cohort has only 1–2 runs, the average is highly unstable and the relative check may overreact. No confidence-level logic applied.
- **Model-switch cost spikes**: A legitimate model upgrade (e.g. cheap → expensive) that increases cost is indistinguishable from wasteful cost spikes.
- **Large-input cost spikes**: A deliberately large prompt causing higher cost is not distinguished from inefficient tool usage.
- **No period-over-period comparison**: Only per-run cost is checked; no cost trend over time.