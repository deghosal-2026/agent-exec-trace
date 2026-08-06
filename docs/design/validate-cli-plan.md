# validate CLI Implementation Plan

> **Goal:** Add `analytics validate` CLI command that runs 35 rule-based detectors (optionally + 6 LLM detectors on a sample) against processed parquet traces, producing JSON distribution/correlation reports.

**Architecture:** New `Validator` class in `trace_pipeline/validator.py` reads parquet files, reconstructs SpanNode trees via parent_span_id grouping, builds RunSummaries via `RunSummaryBuilder`, runs detectors (sync + async), produces terminal summary + JSON reports split by `without-llm/` and `with-llm/`.

**Tech Stack:** pyarrow (parquet read), asyncio (async detectors), json, existing analytics modules (models, detectors, ingest, config)

## Global Constraints

- ruff check . passes, mypy --strict services/analytics passes
- Output to `data/traces/validations/{without-llm,with-llm}/`
- CLI: `validate --input <dir> [--llm-sample <n>] [--output <dir>]`
- Detectors run per trace, exceptions caught, skipped

---

### Task 1: Validator core — parquet loading + tree reconstruction

**Files:**
- Create: `services/analytics/src/analytics/trace_pipeline/validator.py`

**Interfaces:**
- Produces: `Validator` class with `__init__(input_dir, output_dir)`, `async run()` returning `dict`

- [ ] **Step 1: Write the failing test**

```python
# services/analytics/tests/test_validator.py
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from analytics.trace_pipeline.validator import Validator


@pytest.fixture
def sample_parquet_dir():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {
                "trace_id": "t1", "span_id": "root", "parent_span_id": None,
                "operation_name": "invoke_agent", "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00", "duration_ms": 60000,
                "attributes_json": json.dumps({"gen_ai.agent.name": "triage", "gen_ai.agent.version": "v1"}),
                "status": "success", "source_dataset": "test", "source_row_idx": 1,
            },
            {
                "trace_id": "t1", "span_id": "s1", "parent_span_id": "root",
                "operation_name": "execute_tool", "start_time": None,
                "end_time": None, "duration_ms": 100,
                "attributes_json": json.dumps({"gen_ai.tool.name": "search"}),
                "status": "ok", "source_dataset": "test", "source_row_idx": 1,
            },
        ]
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(Path(tmp) / "traces-0001.parquet"))
        yield tmp


@pytest.mark.asyncio
async def test_validator_loads_and_runs_detectors(sample_parquet_dir):
    v = Validator(input_dir=sample_parquet_dir)
    report = await v.run()
    assert report["traces_processed"] == 1
    assert "anomaly_by_type" in report
    assert report["anomaly_count"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest services/analytics/tests/test_validator.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Write Validator class**

```python
# services/analytics/src/analytics/trace_pipeline/validator.py
from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from analytics.config import settings
from analytics.detectors import create_all_detectors
from analytics.detectors.base import BaseDetector
from analytics.ingest import RunSummaryBuilder
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class Validator:
    def __init__(
        self,
        input_dir: str = "data/traces/processed",
        output_dir: str = "data/traces/validations",
        llm_sample: int | None = None,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.llm_sample = llm_sample
        self.detectors: list[BaseDetector] = create_all_detectors()

    async def run(self) -> dict[str, object]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        mode = "with-llm" if self.llm_sample else "without-llm"
        out_dir = self.output_dir / mode
        out_dir.mkdir(parents=True, exist_ok=True)

        traces = list(self._load_traces())
        if self.llm_sample:
            import random
            random.shuffle(traces)
            traces = traces[: self.llm_sample]

        anomalies_by_trace: list[dict[str, object]] = []
        anomaly_counter: Counter[str] = Counter()
        severity_counter: Counter[str] = Counter()
        detector_fire_count: Counter[str] = Counter()
        trace_anomaly_map: dict[str, list[str]] = {}

        for trace_id, summary, spans in traces:
            trace_anomalies: list[str] = []
            for detector in self.detectors:
                if detector.anomaly_type in settings.detector_disabled:
                    continue
                try:
                    result = detector.detect(summary, spans)
                    if isinstance(result, asyncio.Future) or hasattr(result, "__await__"):
                        result = None
                    if result is not None:
                        anomaly_counter[result.anomaly_type] += 1
                        severity_counter[result.severity] += 1
                        detector_fire_count[detector.anomaly_type] += 1
                        trace_anomalies.append(result.anomaly_type)
                except Exception:
                    logger.exception("Detector %s failed for trace %s", detector.anomaly_type, trace_id)

            if trace_anomalies:
                trace_anomaly_map[trace_id] = trace_anomalies
                anomalies_by_trace.append({
                    "trace_id": trace_id,
                    "anomalies": [
                        {"type": t} for t in trace_anomalies
                    ],
                })

        # Correlation matrix
        correlation = self._build_correlation(trace_anomaly_map)

        # Suspicious patterns
        total = len(traces)
        suspicious = {
            dt: round(count / total * 100, 1)
            for dt, count in detector_fire_count.items()
            if total > 0 and count / total > 0.5
        }

        report: dict[str, object] = {
            "traces_processed": total,
            "anomaly_count": sum(anomaly_counter.values()),
            "anomaly_by_type": dict(anomaly_counter.most_common()),
            "anomaly_by_severity": dict(severity_counter),
            "detector_fire_rate": {
                dt: round(count / total * 100, 1) if total else 0
                for dt, count in detector_fire_count.items()
            },
            "suspicious_patterns": suspicious,
            "cross_detector_correlation": correlation,
        }

        # Write JSON reports
        (out_dir / "summary.json").write_text(json.dumps(report, indent=2, default=str))
        (out_dir / "correlation.json").write_text(json.dumps({
            "matrix": correlation,
            "suspicious": suspicious,
        }, indent=2, default=str))
        (out_dir / "traces.json").write_text(json.dumps(anomalies_by_trace, indent=2, default=str))

        return report

    def _load_traces(self) -> list[tuple[str, RunSummary, list[SpanNode]]]:
        traces: list[tuple[str, RunSummary, list[SpanNode]]] = []
        parquet_files = sorted(self.input_dir.rglob("*.parquet"))
        if not parquet_files:
            logger.warning("No parquet files found in %s", self.input_dir)
            return traces

        import pyarrow.parquet as pq

        for pq_file in parquet_files:
            try:
                table = pq.read_table(str(pq_file))
            except Exception:
                logger.warning("Cannot read %s, skipping", pq_file)
                continue

            groups: dict[tuple[str, int], list[SpanNode]] = {}
            for i in range(table.num_rows):
                row = table.slice(i, 1).to_pylist()[0]
                source_row_idx = row.get("source_row_idx", 0)
                key = (str(row["trace_id"]), int(source_row_idx))
                attrs = json.loads(row.get("attributes_json", "{}"))
                span = SpanNode(
                    span_id=str(row["span_id"]),
                    trace_id=str(row["trace_id"]),
                    parent_span_id=str(row["parent_span_id"]) if row["parent_span_id"] else None,
                    operation_name=str(row["operation_name"]),
                    start_time=_parse_dt(row.get("start_time")),
                    end_time=_parse_dt(row.get("end_time")),
                    duration_ms=float(row.get("duration_ms") or 0),
                    attributes=attrs if isinstance(attrs, dict) else {},
                    status=str(row.get("status") or ""),
                )
                groups.setdefault(key, []).append(span)

            for (trace_id, _), spans in groups.items():
                roots = _build_trees(spans)
                if not roots:
                    continue
                summary = RunSummaryBuilder().build(roots)
                traces.append((trace_id, summary, roots))

        logger.info("Loaded %d traces from %d parquet files", len(traces), len(parquet_files))
        return traces

    def _build_correlation(self, trace_map: dict[str, list[str]]) -> dict[str, object]:
        pairs: Counter[tuple[str, str]] = Counter()
        type_counts: Counter[str] = Counter()
        for a_types in trace_map.values():
            for t in a_types:
                type_counts[t] += 1
            for i, t1 in enumerate(a_types):
                for t2 in a_types[i + 1 :]:
                    pairs[(t1, t2)] += 1
                    pairs[(t2, t1)] += 1
        top_pairs = pairs.most_common(20)
        return {
            "top_co_fires": [
                {"pair": list(p), "count": c, "pct": round(c / max(type_counts[p[0]], 1) * 100, 1)}
                for p, c in top_pairs
            ],
            "type_counts": dict(type_counts),
        }


def _parse_dt(val: object) -> str | None:
    if val is None:
        return None
    return str(val)


def _build_trees(spans: list[SpanNode]) -> list[SpanNode]:
    by_id = {s.span_id: s for s in spans}
    roots: list[SpanNode] = []
    for s in spans:
        if s.parent_span_id and s.parent_span_id in by_id:
            parent = by_id[s.parent_span_id]
            if parent.child_spans is None:
                parent.child_spans = []
            parent.child_spans.append(s)
        else:
            roots.append(s)
    return roots
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest services/analytics/tests/test_validator.py -v -s
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/analytics/src/analytics/trace_pipeline/validator.py services/analytics/tests/test_validator.py
git commit -m "feat: add Validator class for batch detector validation against parquet traces"
```

---

### Task 2: Wire validate CLI command

**Files:**
- Modify: `services/analytics/src/analytics/main.py`

**Interfaces:**
- Consumes: `Validator` class from `trace_pipeline.validator`

- [ ] **Step 1: Add validate command**

Add after the `materialize` command in `main.py`:

```python
@main.command("validate")
@click.option("--input", "input_dir", default="data/traces/processed", help="Directory of processed parquet traces")
@click.option("--output", "output_dir", default="data/traces/validations", help="Output directory for reports")
@click.option("--llm-sample", default=None, type=int, help="Sample N traces and include LLM detectors")
def validate_traces(input_dir: str, output_dir: str, llm_sample: int | None) -> None:
    """Run all detectors against processed traces and produce validation reports."""
    from analytics.trace_pipeline.validator import Validator

    async def _run() -> None:
        v = Validator(input_dir=input_dir, output_dir=output_dir, llm_sample=llm_sample)
        report = await v.run()
        total = report["traces_processed"]
        anomaly_count = report["anomaly_count"]
        click.echo(f"\n=== TRACE VALIDATION ({'LLM sample ' + str(llm_sample) if llm_sample else 'rule-based'}) ===")
        click.echo(f"Traces processed: {total}")
        click.echo(f"Anomalies found:   {anomaly_count}")

        by_type = report.get("anomaly_by_type", {})
        if by_type:
            click.echo("Top detectors:")
            for dt, cnt in list(by_type.items())[:10]:
                click.echo(f"  {dt}: {cnt}")

        suspicious = report.get("suspicious_patterns", {})
        if suspicious:
            click.echo("\n⚠ Flagged (>50% fire rate):")
            for dt, pct in suspicious.items():
                click.echo(f"  {dt}: {pct}%")

        corr = report.get("cross_detector_correlation", {})
        top_pairs = corr.get("top_co_fires", [])[:5]
        if top_pairs:
            click.echo("\nCross-detector hotspots:")
            for entry in top_pairs:
                pair = " + ".join(entry["pair"])
                click.echo(f"  {pair}: {entry['count']} traces ({entry['pct']}%)")

        mode = "with-llm" if llm_sample else "without-llm"
        click.echo(f"\nReports: {output_dir}/{mode}/")

    _run_async(_run())
```

- [ ] **Step 2: Test CLI**

```bash
python -m analytics.main validate --help
python -m analytics.main validate --input services/analytics/tests/fixtures 2>&1 | head -5
```

- [ ] **Step 3: Run quality gates**

```bash
ruff check services/analytics && mypy --strict services/analytics && pytest -q services/analytics/tests
```

- [ ] **Step 4: Commit**

```bash
git add services/analytics/src/analytics/main.py
git commit -m "feat: add validate CLI command for batch detector validation"
```
