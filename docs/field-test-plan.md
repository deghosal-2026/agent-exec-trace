# Field-Test Plan — Anomaly Detection

Anomaly detection in v0.1.0 is seeded and deterministic. A dedicated field-test plan is required before production confidence.

## Minimum Future Field-Test Dimensions

1. **Multiple workloads** — detectors must be validated against at least 2 distinct workload types (e.g. code-review, customer-support) to ensure thresholds generalize.
2. **False positive analysis** — after N runs (N >= 100), manually review every fired anomaly and classify as true positive or false positive. Track false-positive rate per detector.
3. **Detector usefulness review** — for each true positive, answer: did this alert lead to operator action? Was the explanation sufficient to triage?
4. **Operator feedback** — collect structured feedback from operators reviewing anomaly inbox: was the severity correct? Was the explanation clear? What additional context was needed?
5. **Threshold tuning** — after field data, produce recommended threshold adjustments per detector per workload type.
6. **Sparse baseline awareness** — cost spike detector should flag low-confidence predictions when baseline cohort has fewer than 5 runs.