"""Batch detector validation against processed parquet traces.

Loads parquet files, reconstructs SpanNode trees, builds RunSummaries, runs all
35 rule-based detectors, and produces distribution/correlation/suspicious-pattern
reports as JSON.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analytics.config import settings
from analytics.detectors import create_all_detectors
from analytics.detectors.base import BaseDetector
from analytics.detectors.llm import (
    ConfusionPatternDetector,
    EmbeddingDriftDetector,
    GoalDriftDetector,
    HallucinationDetector,
    QualityDegradationDetector,
    SemanticLoopDetector,
)
from analytics.ingest import RunSummaryBuilder
from analytics.llm_client import LLMClient
from analytics.models import Anomaly, RunSummary, SpanNode

logger = logging.getLogger(__name__)


class Validator:
    """Batch-run detectors against processed traces and produce validation reports."""

    def __init__(
        self,
        input_dir: str = "data/traces/processed",
        output_dir: str = "data/traces/validations",
        llm_sample: int | None = None,
        resume: bool = False,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.llm_sample = llm_sample
        self.resume = resume
        self.detectors: list[BaseDetector] = create_all_detectors()
        if self.llm_sample:
            self.detectors.extend(create_llm_detectors())
        self._mode_dir: Path | None = None

    def _progress_path(self) -> Path:
        if self._mode_dir is None:
            mode = "with-llm" if self.llm_sample else "without-llm"
            self._mode_dir = self.output_dir / mode
        return self._mode_dir / "progress.json"

    def _load_progress(self) -> set[tuple[str, str]]:
        path = self._progress_path()
        if not path.exists():
            return set()
        try:
            data = json.loads(path.read_text())
            seen: list[list[str]] = data.get("completed_traces", [])
            progress_set: set[tuple[str, str]] = {
                (str(item[0]), str(item[1])) for item in seen if len(item) == 2
            }
            logger.info(
                "Resume: %d traces already completed, %d detections",
                len(progress_set),
                data.get("anomaly_count", 0),
            )
            return progress_set
        except (json.JSONDecodeError, KeyError):
            return set()

    def _save_progress(
        self,
        completed: set[tuple[str, str]],
        anomaly_counter: Counter[str],
        severity_counter: Counter[str],
        detector_fire_count: Counter[str],
        trace_anomaly_map: dict[str, list[str]],
        total: int,
    ) -> None:
        path = self._progress_path()
        path.write_text(
            json.dumps(
                {
                    "completed_traces": list(sorted(completed)),
                    "completed_count": len(completed),
                    "total_in_batch": total,
                    "anomaly_count": sum(anomaly_counter.values()),
                    "anomaly_by_type": dict(anomaly_counter.most_common()),
                    "anomaly_by_severity": dict(severity_counter),
                    "detector_fire_rate": {
                        dt: round(count / max(total, 1) * 100, 1)
                        for dt, count in detector_fire_count.items()
                    },
                },
                indent=2,
                default=str,
            )
        )

    async def run(self) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        mode = "with-llm" if self.llm_sample else "without-llm"
        out_dir = self.output_dir / mode
        out_dir.mkdir(parents=True, exist_ok=True)

        if self.llm_sample:
            pool_size = self.llm_sample * 10
            traces = self._load_traces(max_traces=pool_size)
            if len(traces) > pool_size:
                traces = traces[:pool_size]
            traces = traces[::10][:self.llm_sample]
        else:
            traces = self._load_traces()

        if self.resume:
            completed: set[tuple[str, str]] = self._load_progress()
        else:
            completed = set()

        anomalies_by_trace: list[dict[str, Any]] = []
        anomaly_counter: Counter[str] = Counter()
        severity_counter: Counter[str] = Counter()
        detector_fire_count: Counter[str] = Counter()
        trace_anomaly_map: dict[str, list[str]] = {}
        detector_errors: dict[str, str] = {}
        skipped: dict[str, int] = {}
        total = len(traces)
        processed = 0

        empty_response_sources: Counter[str] = Counter()
        empty_response_examples: list[dict[str, str]] = []

        for _idx, (trace_id, summary, spans, source_file) in enumerate(traces):
            trace_key = (trace_id, str(summary.run_id))
            if trace_key in completed:
                processed += 1
                continue

            suppress_empty_response = _is_output_unavailable_trace(spans)
            trace_anomalies: list[str] = []
            for detector in self.detectors:
                d_type = detector.anomaly_type
                if d_type in settings.detector_disabled:
                    skipped[d_type] = skipped.get(d_type, 0) + 1
                    continue
                if d_type == "empty_response" and suppress_empty_response:
                    skipped[d_type] = skipped.get(d_type, 0) + 1
                    continue
                try:
                    if (
                        hasattr(type(detector), "detect_async")
                        and type(detector).detect_async is not BaseDetector.detect_async
                    ):
                        raw: Any = await detector.detect_async(summary, spans)
                    else:
                        raw = detector.detect(summary, spans)

                    if raw is not None and not _is_awaitable(raw):
                        anomaly: Anomaly = raw
                        detector_fire_count[d_type] += 1
                        anomaly_counter[d_type] += 1
                        severity_counter[anomaly.severity] += 1
                        trace_anomalies.append(d_type)
                        if d_type == "empty_response":
                            empty_response_sources[source_file] += 1
                            if len(empty_response_examples) < 200:
                                empty_response_examples.append(
                                    {
                                        "trace_id": trace_id,
                                        "run_id": str(summary.run_id),
                                        "source_file": source_file,
                                    }
                                )
                except NotImplementedError:
                    detector_errors.setdefault(d_type, "not implemented (needs pool)")
                    skipped[d_type] = skipped.get(d_type, 0) + 1
                except Exception:
                    logger.exception(
                        "Detector %s failed for trace %s", d_type, trace_id
                    )
                    detector_errors.setdefault(d_type, "exception")

            if trace_anomalies:
                trace_anomaly_map[trace_id] = trace_anomalies
                anomalies_by_trace.append(
                    {
                        "trace_id": trace_id,
                        "anomalies": [{"type": t} for t in trace_anomalies],
                    }
                )

            completed.add(trace_key)
            processed += 1

            if processed % 5000 == 0:
                logger.info(
                    "Processed %d/%d traces, %d anomalies",
                    processed,
                    total,
                    len(anomalies_by_trace),
                )
                if self.resume:
                    self._save_progress(
                        completed,
                        anomaly_counter,
                        severity_counter,
                        detector_fire_count,
                        trace_anomaly_map,
                        total,
                    )

        correlation = _build_correlation(trace_anomaly_map)

        suspicious: dict[str, float] = {}
        if total > 0:
            suspicious = {
                dt: round(count / total * 100, 1)
                for dt, count in detector_fire_count.items()
                if count / total > 0.5
            }

        report: dict[str, Any] = {
            "traces_processed": processed,
            "traces_skipped_resume": len(completed) - processed if self.resume else 0,
            "traces_with_anomalies": len(anomalies_by_trace),
            "anomaly_count": sum(anomaly_counter.values()),
            "anomaly_by_type": dict(anomaly_counter.most_common()),
            "anomaly_by_severity": dict(severity_counter),
            "detector_fire_rate": {
                dt: round(count / total * 100, 1) if total else 0
                for dt, count in detector_fire_count.items()
            },
            "suspicious_patterns": suspicious,
            "cross_detector_correlation": correlation,
            "skipped_detectors": skipped,
            "detector_errors": detector_errors,
        }

        (out_dir / "summary.json").write_text(
            json.dumps(report, indent=2, default=str)
        )
        (out_dir / "correlation.json").write_text(
            json.dumps(
                {"matrix": correlation, "suspicious": suspicious}, indent=2, default=str
            )
        )
        (out_dir / "traces.json").write_text(
            json.dumps(anomalies_by_trace, indent=2, default=str)
        )
        (out_dir / "empty_response_sources.json").write_text(
            json.dumps(
                {
                    "count_by_source_file": dict(empty_response_sources.most_common()),
                    "examples": empty_response_examples,
                },
                indent=2,
                default=str,
            )
        )

        if self.resume:
            self._save_progress(
                completed,
                anomaly_counter,
                severity_counter,
                detector_fire_count,
                trace_anomaly_map,
                total,
            )

        logger.info("Reports written to %s", out_dir)
        return report

    def _load_traces(
        self, max_traces: int | None = None,
    ) -> list[tuple[str, RunSummary, list[SpanNode], str]]:
        traces: list[tuple[str, RunSummary, list[SpanNode], str]] = []
        parquet_files = sorted(self.input_dir.rglob("*.parquet"))
        if not parquet_files:
            logger.warning("No parquet files found in %s", self.input_dir)
            return traces

        import pyarrow.parquet as pq

        for pq_file in parquet_files:
            try:
                table = pq.read_table(str(pq_file))  # type: ignore[no-untyped-call]
            except Exception:
                logger.warning("Cannot read %s, skipping", pq_file)
                continue

            groups: dict[tuple[str, int], list[SpanNode]] = {}
            rows = table.to_pylist()
            for row in rows:
                source_row_idx = row.get("source_row_idx", 0)
                idx_val = int(source_row_idx) if source_row_idx is not None else 0
                key = (str(row["trace_id"]), idx_val)
                attrs_raw = row.get("attributes_json", "{}")
                attrs: dict[str, Any] = (
                    json.loads(attrs_raw) if isinstance(attrs_raw, str) else {}
                )
                if not isinstance(attrs, dict):
                    attrs = {}
                attrs = _normalize_attrs(attrs, str(row.get("operation_name", "")))
                duration_raw = row.get("duration_ms")
                duration: int | None = (
                    int(duration_raw) if duration_raw is not None else None
                )

                operation_name = _normalize_operation_name(
                    str(row.get("operation_name", "")), attrs
                )

                span = SpanNode(
                    span_id=str(row["span_id"]),
                    trace_id=str(row["trace_id"]),
                    parent_span_id=(
                        str(row["parent_span_id"])
                        if row.get("parent_span_id")
                        else None
                    ),
                    operation_name=operation_name,
                    start_time=_parse_dt(row.get("start_time")),
                    end_time=_parse_dt(row.get("end_time")),
                    duration_ms=duration,
                    attributes=attrs,
                    status=str(row.get("status") or ""),
                )
                groups.setdefault(key, []).append(span)

            for (trace_id, _), spans in groups.items():
                roots = _build_trees(spans)
                if not roots:
                    continue
                summary = RunSummaryBuilder.build_from_span_tree(roots, trace_id)
                if summary is not None:
                    traces.append((trace_id, summary, roots, str(pq_file)))

                if max_traces is not None and len(traces) >= max_traces:
                    break

        logger.info(
            "Loaded %d traces from %d parquet files", len(traces), len(parquet_files)
        )
        return traces


def _is_awaitable(obj: Any) -> bool:
    return isinstance(obj, (asyncio.Future, asyncio.Task)) or hasattr(obj, "__await__")


def create_llm_detectors() -> list[BaseDetector]:
    client = LLMClient()
    return [
        EmbeddingDriftDetector(client),
        SemanticLoopDetector(client),
        HallucinationDetector(client),
        GoalDriftDetector(client),
        QualityDegradationDetector(client),
        ConfusionPatternDetector(client),
    ]


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    raw = str(val)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _normalize_attrs(attrs: dict[str, Any], operation_name: str) -> dict[str, Any]:
    normalized = dict(attrs)
    source_role = str(normalized.get("from", "")).lower().strip()
    source_value = normalized.get("value")

    tool_blob = _parse_tool_response_blob(source_value) if isinstance(source_value, str) else None

    if not normalized.get("gen_ai.response.content"):
        for key in (
            "assistant_response",
            "completion",
            "message_content",
            "content",
            "answer",
            "tool_output",
        ):
            value = normalized.get(key)
            if isinstance(value, str) and value.strip():
                normalized["gen_ai.response.content"] = value
                break
        if (
            not normalized.get("gen_ai.response.content")
            and source_role in {"gpt", "assistant", "ai", "model"}
            and isinstance(source_value, str)
            and source_value.strip()
        ):
            normalized["gen_ai.response.content"] = source_value

    if operation_name == "execute_tool":
        if not normalized.get("gen_ai.tool.name"):
            for key in ("tool_name", "name", "label"):
                value = normalized.get(key)
                if isinstance(value, str) and value.strip():
                    normalized["gen_ai.tool.name"] = value
                    break
            if tool_blob and isinstance(tool_blob.get("name"), str):
                normalized["gen_ai.tool.name"] = tool_blob["name"]

        if "gen_ai.tool.result" not in normalized:
            for key in ("tool_output", "output", "result", "assistant_response"):
                value = normalized.get(key)
                if value is not None:
                    normalized["gen_ai.tool.result"] = value
                    break
            if tool_blob and "content" in tool_blob:
                normalized["gen_ai.tool.result"] = tool_blob["content"]

    if (
        source_role == "tool"
        and isinstance(source_value, str)
        and source_value.strip()
        and "gen_ai.tool.result" not in normalized
    ):
        normalized["gen_ai.tool.result"] = (
            tool_blob.get("content") if tool_blob and "content" in tool_blob else source_value
        )

    if "gen_ai.usage.prompt_tokens" not in normalized:
        prompt_tokens = normalized.get("input_tokens")
        if isinstance(prompt_tokens, int | float):
            normalized["gen_ai.usage.prompt_tokens"] = int(prompt_tokens)

    if "gen_ai.usage.completion_tokens" not in normalized:
        completion_tokens = normalized.get("output_tokens")
        if isinstance(completion_tokens, int | float):
            normalized["gen_ai.usage.completion_tokens"] = int(completion_tokens)

    if "gen_ai.agent.run.cost.total" not in normalized:
        cost = normalized.get("cost_usd")
        if isinstance(cost, int | float):
            normalized["gen_ai.agent.run.cost.total"] = float(cost)

    return normalized


def _normalize_operation_name(operation_name: str, attrs: dict[str, Any]) -> str:
    if operation_name != "unknown":
        return operation_name

    source_role = str(attrs.get("from", "")).lower().strip()
    if source_role == "tool":
        return "execute_tool"
    if source_role in {"gpt", "assistant", "ai", "model"}:
        return "plan"
    if source_role in {"human", "user", "system"}:
        return "invoke_agent"
    return operation_name


def _parse_tool_response_blob(value: str) -> dict[str, Any] | None:
    start_tag = "<tool_response>"
    end_tag = "</tool_response>"
    if start_tag not in value or end_tag not in value:
        return None

    try:
        payload = value.split(start_tag, 1)[1].split(end_tag, 1)[0].strip()
        parsed = json.loads(payload)
    except (IndexError, json.JSONDecodeError):
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


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


def _build_correlation(trace_map: dict[str, list[str]]) -> dict[str, Any]:
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
            {
                "pair": list(p),
                "count": c,
                "pct": round(c / max(type_counts.get(p[0], 1), 1) * 100, 1),
            }
            for p, c in top_pairs
        ],
        "type_counts": dict(type_counts),
    }


def _is_output_unavailable_trace(spans: list[SpanNode]) -> bool:
    saw_scratchpad = False
    saw_output_capable_field = False

    for span in spans:
        for node in _walk_all_spans(span):
            attrs = node.attributes
            if any(key in attrs for key in ("scratchpad", "reasoning", "answer_wthink")):
                saw_scratchpad = True

            for key in (
                "gen_ai.response.content",
                "assistant_response",
                "completion",
                "message_content",
                "content",
                "answer",
                "value",
            ):
                val = attrs.get(key)
                if (
                    isinstance(val, str)
                    and val.strip()
                    and (
                        key != "value"
                        or str(attrs.get("from", "")).lower().strip()
                        in {"gpt", "assistant", "ai", "model", "tool"}
                    )
                ):
                    saw_output_capable_field = True
                    break
            if saw_output_capable_field:
                break
        if saw_output_capable_field:
            break

    return saw_scratchpad and not saw_output_capable_field


def _walk_all_spans(root: SpanNode) -> list[SpanNode]:
    nodes = [root]
    for child in root.child_spans:
        nodes.extend(_walk_all_spans(child))
    return nodes
