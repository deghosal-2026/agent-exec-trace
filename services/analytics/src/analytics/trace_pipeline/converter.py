"""Trace format converter.

Converts traces from Hugging Face dataset formats to OTel-compatible
``SpanNode`` trees.  Supports multiple source formats through auto-detection:
LangChain/LangSmith, generic JSON, array-based, and chat/text formats.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from analytics.models import SpanNode

logger = logging.getLogger(__name__)


OPERATION_MAP: dict[str, str] = {
    "tool_call": "execute_tool",
    "tool": "execute_tool",
    "execute": "execute_tool",
    "action": "execute_tool",
    "function_call": "execute_tool",
    "think": "plan",
    "plan": "plan",
    "reason": "plan",
    "thought": "plan",
    "thinking": "plan",
    "retrieve": "retrieval",
    "search": "retrieval",
    "lookup": "retrieval",
    "query": "retrieval",
    "rag": "retrieval",
    "agent_run": "invoke_agent",
    "invoke": "invoke_agent",
    "run": "invoke_agent",
    "agent": "invoke_agent",
    "llm_call": "invoke_agent",
    "llm": "invoke_agent",
    "chat": "invoke_agent",
    "completion": "invoke_agent",
    "observe": "observation",
    "watch": "observation",
    "monitor": "observation",
    "evaluate": "observation",
    "memory": "memory",
    "remember": "memory",
    "store": "memory",
    "recall": "memory",
    "parse": "transform",
    "format": "transform",
    "transform": "transform",
    "read": "read",
    "write": "write",
    "edit": "write",
    "generate": "invoke_agent",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def _parse_timestamp(value: object) -> datetime | None:
    """Parse a timestamp from various formats into UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, int | float):
        secs = float(value)
        if secs > 1e12:
            return datetime.fromtimestamp(secs / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(secs, tz=timezone.utc)
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(str(value), fmt)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
    return None


def _infer_operation_name(step: Mapping[str, object]) -> str:
    """Map source-specific names to OTel operation names."""
    for key in ("type", "run_type", "name", "action", "role", "operation", "kind"):
        val = step.get(key)
        if isinstance(val, str) and val:
            lower = val.lower().strip()
            if lower in OPERATION_MAP:
                return OPERATION_MAP[lower]
            for pattern, mapped in OPERATION_MAP.items():
                if pattern in lower:
                    return mapped
            if lower == "user" or lower == "human":
                return "invoke_agent"
            if lower == "assistant" or lower == "ai":
                return "plan"
            if lower == "system":
                return "invoke_agent"
            if lower in ("function", "tool_use", "tool_call"):
                return "execute_tool"
            return lower
    return "unknown"


def _extract_status(step: Mapping[str, object]) -> str | None:
    """Extract status from a step dict."""
    for key in ("status", "success", "error", "outcome", "result"):
        val = step.get(key)
        if val is not None:
            if isinstance(val, bool):
                return "ok" if val else "error"
            if isinstance(val, str):
                lower = val.lower()
                if lower in ("ok", "success", "completed", "done"):
                    return "ok"
                if lower in ("error", "failed", "failure"):
                    return "error"
            if isinstance(val, dict):
                return "ok"
    return None


def _sanitize_attrs(attrs: Mapping[str, object]) -> dict[str, object]:
    """Convert values to JSON-serializable types for SpanNode attributes."""
    sanitized: dict[str, object] = {}
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, str | int | float | bool):
            sanitized[k] = v
        elif isinstance(v, datetime):
            sanitized[k] = v.isoformat()
        elif isinstance(v, list | dict):
            import json as _json

            try:
                sanitized[k] = _json.dumps(v, default=str)
            except (TypeError, ValueError):
                sanitized[k] = str(v)
        else:
            sanitized[k] = str(v)
    return sanitized


class TraceConverter:
    """Convert traces from various source formats to SpanNode trees.

    Auto-detects format based on field inspection and applies the appropriate
    conversion strategy.  Handles LangChain, generic JSON, array, and chat/text
    formats, falling back to best-effort conversion when the format is unknown.
    """

    def convert_batch(
        self,
        dataset_id: str,
        rows: Sequence[Mapping[str, object]],
    ) -> list[list[SpanNode]]:
        """Convert all rows from a dataset, auto-detecting format.

        Args:
            dataset_id: source dataset identifier (for logging/tracing).
            rows: list of row dicts from the HF dataset.

        Returns:
            List of SpanNode trees, one per input row.
        """
        if not rows:
            return []

        converter: Any = self._detect_format(rows)
        logger.info("Using '%s' converter for dataset %s", converter.__name__, dataset_id)

        results: list[list[SpanNode]] = []
        for idx, row in enumerate(rows):
            try:
                spans = converter(row)
                results.append(spans)
            except Exception:
                logger.warning(
                    "Conversion failed for row %d in dataset %s, skipping",
                    idx,
                    dataset_id,
                    exc_info=True,
                )
                results.append([])
        return results

    def _detect_format(self, rows: Sequence[Mapping[str, object]]) -> Any:
        """Inspect a sample of rows to determine the best converter."""
        if not rows:
            return self._convert_generic_json

        sample = rows[0]
        keys = set(sample.keys())

        if "run_type" in keys and "child_runs" in keys:
            return self._convert_langchain_trace
        if "messages" in keys:
            return self._convert_chat_trace
        if "conversation" in keys:
            return self._convert_chat_trace
        if "steps" in keys:
            return self._convert_steps_trace
        if "spans" in keys or "traces" in keys:
            return self._convert_structured_trace
        if "actions" in keys:
            return self._convert_steps_trace
        if "turns" in keys:
            return self._convert_steps_trace
        if any(isinstance(v, list) for v in sample.values()):
            for _k, v in sample.items():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    return self._convert_nested_list_trace
        return self._convert_generic_json

    def _convert_langchain_trace(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert LangChain/LangSmith trace format.

        LangChain traces have: id, run_type, inputs, outputs, child_runs,
        start_time, end_time, error, extra (metadata).
        """
        trace_id = str(row.get("trace_id", row.get("id", _generate_id("tr_"))))

        def _convert_run(run: Mapping[str, object], parent_id: str | None = None) -> SpanNode:
            span_id = str(run.get("id", _generate_id("sp_")))
            operation = _infer_operation_name(run)
            start_time = _parse_timestamp(run.get("start_time", run.get("start")))
            end_time = _parse_timestamp(run.get("end_time", run.get("end")))
            error = run.get("error")
            status: str | None = "error" if error else "ok"

            duration_ms: int | None = None
            if start_time and end_time:
                duration_ms = int((end_time - start_time).total_seconds() * 1000)

            extra = run.get("extra") or run.get("metadata") or {}
            if isinstance(extra, dict):
                attrs: dict[str, object] = dict(extra)
            else:
                attrs = {}
            for key in ("inputs", "outputs", "name", "run_type", "tags"):
                val = run.get(key)
                if val is not None:
                    attrs[key] = val

            children: list[SpanNode] = []
            child_runs = run.get("child_runs", [])
            if isinstance(child_runs, list):
                for child in child_runs:
                    if isinstance(child, dict):
                        children.append(_convert_run(child, parent_id=span_id))

            return SpanNode(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_id,
                operation_name=operation,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                attributes=_sanitize_attrs(attrs),
                status=status,
                child_spans=children,
            )

        root = _convert_run(row, parent_id=None)
        return [root]

    def _convert_chat_trace(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert traces stored as chat message lists.

        Creates a root span with child spans for each message turn.
        """
        trace_id = _generate_id("tr_")
        root_span_id = _generate_id("sp_")

        messages = row.get("messages", row.get("conversation", []))
        if not isinstance(messages, list):
            messages = []

        first_ts: datetime | None = None
        last_ts: datetime | None = None

        children: list[SpanNode] = []
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue

            span_id = _generate_id("sp_")
            role = str(msg.get("role", msg.get("type", "unknown")))
            content = msg.get("content", "")
            op_name = _infer_operation_name({"role": role})
            ts = _parse_timestamp(msg.get("timestamp", msg.get("ts", msg.get("time"))))

            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            children.append(
                SpanNode(
                    span_id=span_id,
                    trace_id=trace_id,
                    parent_span_id=root_span_id,
                    operation_name=op_name,
                    start_time=ts,
                    attributes=_sanitize_attrs(
                        {
                            "role": role,
                            "content": str(content)[:500],
                            "turn_index": i,
                        }
                    ),
                )
            )

        duration_ms: int | None = None
        if first_ts and last_ts:
            duration_ms = int((last_ts - first_ts).total_seconds() * 1000)

        root = SpanNode(
            span_id=root_span_id,
            trace_id=trace_id,
            parent_span_id=None,
            operation_name="invoke_agent",
            start_time=first_ts or _now_utc(),
            end_time=last_ts,
            duration_ms=duration_ms,
            attributes=_sanitize_attrs(
                {
                    "message_count": len(children),
                    "source": "chat_conversion",
                }
            ),
            status="ok",
            child_spans=children,
        )

        return [root]

    def _convert_steps_trace(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert traces stored as an array of execution steps.

        Each element in ``steps``/``actions``/``turns`` becomes a child span
        of a synthetic root span.
        """
        trace_id = _generate_id("tr_")
        root_span_id = _generate_id("sp_")

        steps_key = ""
        for k in ("steps", "actions", "turns", "events"):
            if k in row and isinstance(row[k], list):
                steps_key = k
                break

        if not steps_key:
            return self._convert_generic_json(row)

        steps = row[steps_key]
        if not isinstance(steps, list):
            steps = []

        first_ts: datetime | None = None
        last_ts: datetime | None = None

        children: list[SpanNode] = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            span_id = _generate_id("sp_")
            op_name = _infer_operation_name(step)
            ts = _parse_timestamp(step.get("timestamp", step.get("ts", step.get("time"))))
            status = _extract_status(step)

            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            elif not children:
                ts = _now_utc()
                first_ts = ts
                last_ts = ts

            extra_attrs: dict[str, object] = {}
            for key in step:
                if key not in (
                    "type",
                    "name",
                    "action",
                    "role",
                    "timestamp",
                    "ts",
                    "time",
                    "status",
                    "error",
                ):
                    extra_attrs[key] = step[key]

            children.append(
                SpanNode(
                    span_id=span_id,
                    trace_id=trace_id,
                    parent_span_id=root_span_id,
                    operation_name=op_name,
                    start_time=ts,
                    attributes=_sanitize_attrs({"step_index": i, **extra_attrs}),
                    status=status,
                )
            )

        duration_ms: int | None = None
        if first_ts and last_ts:
            duration_ms = int((last_ts - first_ts).total_seconds() * 1000)

        root = SpanNode(
            span_id=root_span_id,
            trace_id=trace_id,
            parent_span_id=None,
            operation_name="invoke_agent",
            start_time=first_ts or _now_utc(),
            end_time=last_ts,
            duration_ms=duration_ms,
            attributes=_sanitize_attrs({"step_count": len(children), "steps_key": steps_key}),
            status="ok",
            child_spans=children,
        )

        return [root]

    def _convert_structured_trace(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert pre-structured trace data with spans/traces field."""
        spans_data = row.get("spans", row.get("traces", []))
        if isinstance(spans_data, dict):
            return self._convert_generic_json(spans_data)
        if not isinstance(spans_data, list):
            return self._convert_generic_json(row)

        trace_id = str(row.get("trace_id", _generate_id("tr_")))
        root_span_id = _generate_id("sp_")

        children: list[SpanNode] = []
        for item in spans_data:
            if not isinstance(item, dict):
                continue

            span_id = str(item.get("span_id", item.get("id", _generate_id("sp_"))))
            parent_id = item.get("parent_span_id", item.get("parent_id", root_span_id))
            if parent_id is None or (isinstance(parent_id, str) and parent_id == ""):
                parent_id = None

            op_name = _infer_operation_name(item)
            start_time = _parse_timestamp(item.get("start_time", item.get("start")))
            end_time = _parse_timestamp(item.get("end_time", item.get("end")))
            status = _extract_status(item)

            duration_ms: int | None = None
            if start_time and end_time:
                duration_ms = int((end_time - start_time).total_seconds() * 1000)

            attrs: dict[str, object] = {}
            for key in item:
                if key not in (
                    "span_id",
                    "id",
                    "parent_span_id",
                    "parent_id",
                    "start_time",
                    "start",
                    "end_time",
                    "end",
                    "type",
                    "name",
                    "status",
                    "error",
                    "operation_name",
                ):
                    attrs[key] = item[key]

            children.append(
                SpanNode(
                    span_id=span_id,
                    trace_id=trace_id,
                    parent_span_id=parent_id,
                    operation_name=op_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms,
                    attributes=_sanitize_attrs(attrs),
                    status=status,
                )
            )

        if not children:
            return self._convert_generic_json(row)

        spans_map = {s.span_id: s for s in children}
        roots: list[SpanNode] = []
        for s in children:
            if s.parent_span_id is None or s.parent_span_id not in spans_map:
                s.parent_span_id = None
                roots.append(s)
            elif s.parent_span_id in spans_map:
                spans_map[s.parent_span_id].child_spans.append(s)

        return roots

    def _convert_nested_list_trace(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert rows where a value is a list of dicts (array-based trace)."""
        list_field: str = ""
        list_data: list[object] = []
        for k, v in row.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                list_field = k
                list_data = v
                break

        if not list_field:
            return self._convert_generic_json(row)

        wrapped: dict[str, object] = dict(row)
        wrapped["steps"] = list_data
        del wrapped[list_field]
        return self._convert_steps_trace(wrapped)

    def _convert_generic_json(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert arbitrary JSON row with best-effort field detection.

        Tries to find timing, status, and descriptive fields to construct
        a minimal span tree.  Returns an empty list if nothing useful is found.
        """
        trace_id = _generate_id("tr_")

        start_time: datetime | None = None
        end_time: datetime | None = None
        status: str | None = None
        op_name = "unknown"
        attrs: dict[str, object] = {}

        for key, val in row.items():
            if key in ("start_time", "start", "created_at", "timestamp"):
                start_time = _parse_timestamp(val) or start_time
            elif key in ("end_time", "end", "completed_at", "finished_at"):
                end_time = _parse_timestamp(val) or end_time
            elif key in ("status", "success"):
                status = _extract_status({"status": val})
            elif key in ("error", "error_message", "exception"):
                if val is not None and val != "" and val is not False:
                    status = "error"
                    attrs["error"] = str(val)
            elif key in ("type", "name", "operation", "action"):
                op_name = _infer_operation_name({"name": val})
            else:
                attrs[key] = val

        if start_time is None and end_time is None:
            start_time = _now_utc()

        duration_ms: int | None = None
        if start_time and end_time:
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

        root = SpanNode(
            span_id=_generate_id("sp_"),
            trace_id=trace_id,
            parent_span_id=None,
            operation_name=op_name,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            attributes=_sanitize_attrs(attrs),
            status=status or "ok",
        )

        return [root]

    def validate_spans(self, spans: list[SpanNode]) -> list[str]:
        """Validate converted spans.

        Checks for: missing trace_id, missing span_id, invalid parent references,
        and cycles in the tree.

        Args:
            spans: list of root SpanNodes with populated child_spans.

        Returns:
            List of validation error strings (empty list means valid).
        """
        errors: list[str] = []

        all_spans: dict[str, SpanNode] = {}

        def collect(node: SpanNode) -> None:
            if node.span_id in all_spans:
                errors.append(f"Duplicate span_id: {node.span_id}")
            all_spans[node.span_id] = node
            for child in node.child_spans:
                collect(child)

        for root in spans:
            collect(root)

        for span_id, node in all_spans.items():
            if not node.trace_id:
                errors.append(f"Span {span_id}: missing trace_id")
            if not node.span_id:
                errors.append(f"Span {span_id}: missing span_id (should not happen)")
            if node.parent_span_id and node.parent_span_id not in all_spans:
                errors.append(f"Span {span_id}: parent {node.parent_span_id} not found in tree")

        visited: set[str] = set()
        in_stack: set[str] = set()

        def check_cycles(node: SpanNode) -> None:
            if node.span_id in in_stack:
                errors.append(f"Cycle detected involving span {node.span_id}")
                return
            if node.span_id in visited:
                return
            visited.add(node.span_id)
            in_stack.add(node.span_id)
            for child in node.child_spans:
                check_cycles(child)
            in_stack.discard(node.span_id)

        for root in spans:
            check_cycles(root)

        return errors

    def _convert_array_trace(self, row: Mapping[str, object]) -> list[SpanNode]:
        """Convert traces stored as arrays of events/actions.

        Each element represents one step: extract action name, timing, result.
        """
        return self._convert_steps_trace(row)
