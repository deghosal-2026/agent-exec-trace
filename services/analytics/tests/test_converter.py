"""Tests for trace conversion pipeline — Jaeger/HF JSON → SpanNode trees."""

from __future__ import annotations

from datetime import datetime, timezone

from analytics.models import SpanNode
from analytics.trace_pipeline.converter import (
    OPERATION_MAP,
    TraceConverter,
    _extract_status,
    _infer_operation_name,
    _now_utc,
    _parse_timestamp,
    _sanitize_attrs,
)


# =============================================================================
# OPERATION_MAP
# =============================================================================

def test_operation_map_has_expected_mappings() -> None:
    assert OPERATION_MAP["tool_call"] == "execute_tool"
    assert OPERATION_MAP["tool"] == "execute_tool"
    assert OPERATION_MAP["think"] == "plan"
    assert OPERATION_MAP["thinking"] == "plan"
    assert OPERATION_MAP["thought"] == "plan"
    assert OPERATION_MAP["retrieve"] == "retrieval"
    assert OPERATION_MAP["search"] == "retrieval"


# =============================================================================
# _now_utc
# =============================================================================

def test_now_utc_returns_datetime_with_utc_tz() -> None:
    dt = _now_utc()
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
    assert dt.tzinfo == timezone.utc


# =============================================================================
# _parse_timestamp
# =============================================================================

def test_parse_timestamp_returns_none_for_none() -> None:
    assert _parse_timestamp(None) is None


def test_parse_timestamp_handles_datetime_with_utc() -> None:
    dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    result = _parse_timestamp(dt)
    assert result == dt


def test_parse_timestamp_handles_datetime_without_tz() -> None:
    dt = datetime(2024, 1, 15, 10, 30, 0)
    result = _parse_timestamp(dt)
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_handles_unix_seconds() -> None:
    result = _parse_timestamp(1700000000)
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_handles_unix_milliseconds() -> None:
    result = _parse_timestamp(1700000000000)
    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result.year == 2023


def test_parse_timestamp_handles_iso_string_with_z() -> None:
    result = _parse_timestamp("2024-01-15T10:30:00Z")
    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15


def test_parse_timestamp_handles_iso_string_with_offset() -> None:
    result = _parse_timestamp("2024-01-15T10:30:00+05:00")
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_handles_iso_string_with_microseconds() -> None:
    result = _parse_timestamp("2024-01-15T10:30:00.123456Z")
    assert result is not None


def test_parse_timestamp_handles_space_separated_format() -> None:
    result = _parse_timestamp("2024-01-15 10:30:00")
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_handles_date_only_string() -> None:
    result = _parse_timestamp("2024-01-15")
    assert result is None


def test_parse_timestamp_handles_garbage_string() -> None:
    assert _parse_timestamp("not-a-date") is None


def test_parse_timestamp_handles_zero_int() -> None:
    result = _parse_timestamp(0)
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_handles_float_seconds() -> None:
    result = _parse_timestamp(1700000000.5)
    assert result is not None


# =============================================================================
# _infer_operation_name
# =============================================================================

def test_infer_maps_type_key() -> None:
    assert _infer_operation_name({"type": "tool_call"}) == "execute_tool"


def test_infer_maps_run_type_key() -> None:
    assert _infer_operation_name({"run_type": "think"}) == "plan"


def test_infer_maps_name_key() -> None:
    assert _infer_operation_name({"name": "search_kb"}) == "retrieval"


def test_infer_handles_user_role() -> None:
    assert _infer_operation_name({"role": "user"}) == "invoke_agent"
    assert _infer_operation_name({"role": "human"}) == "invoke_agent"


def test_infer_handles_assistant_role() -> None:
    assert _infer_operation_name({"role": "assistant"}) == "plan"
    assert _infer_operation_name({"role": "ai"}) == "plan"


def test_infer_handles_system_role() -> None:
    assert _infer_operation_name({"role": "system"}) == "invoke_agent"


def test_infer_handles_tool_aliases() -> None:
    assert _infer_operation_name({"type": "function_call"}) == "execute_tool"
    assert _infer_operation_name({"type": "tool_use"}) == "execute_tool"


def test_infer_handles_operation_key() -> None:
    assert _infer_operation_name({"operation": "search"}) == "retrieval"


def test_infer_handles_kind_key() -> None:
    assert _infer_operation_name({"kind": "tool_call"}) == "execute_tool"


def test_infer_handles_action_key() -> None:
    assert _infer_operation_name({"action": "think"}) == "plan"


def test_infer_returns_lowercase_raw_value_for_unknown() -> None:
    assert _infer_operation_name({"type": "CustomOp"}) == "customop"


def test_infer_returns_unknown_for_empty_dict() -> None:
    assert _infer_operation_name({}) == "unknown"


def test_infer_returns_unknown_for_no_keys() -> None:
    assert _infer_operation_name({"other": "value"}) == "unknown"


def test_infer_key_priority_type_beats_run_type() -> None:
    assert _infer_operation_name({"type": "tool_call", "run_type": "think"}) == "execute_tool"


# =============================================================================
# _extract_status
# =============================================================================

def test_extract_status_true_is_ok() -> None:
    assert _extract_status({"success": True}) == "ok"


def test_extract_status_false_is_error() -> None:
    assert _extract_status({"success": False}) == "error"


def test_extract_status_ok_strings() -> None:
    for s in ("ok", "success", "completed", "done"):
        assert _extract_status({"status": s}) == "ok"


def test_extract_status_error_strings() -> None:
    for s in ("error", "failed", "failure"):
        assert _extract_status({"status": s}) == "error"


def test_extract_status_dict_is_ok() -> None:
    assert _extract_status({"result": {"ok": True}}) == "ok"


def test_extract_status_none_for_missing() -> None:
    assert _extract_status({}) is None


def test_extract_status_none_for_none_value() -> None:
    assert _extract_status({"status": None}) is None


def test_extract_status_priority_status_beats_success() -> None:
    assert _extract_status({"status": "error", "success": True}) == "error"


# =============================================================================
# _sanitize_attrs
# =============================================================================

def test_sanitize_passes_string() -> None:
    assert _sanitize_attrs({"key": "value"}) == {"key": "value"}


def test_sanitize_passes_int_float_bool() -> None:
    result = _sanitize_attrs({"a": 1, "b": 2.5, "c": True})
    assert result == {"a": 1, "b": 2.5, "c": True}


def test_sanitize_drops_none() -> None:
    assert "none_key" not in _sanitize_attrs({"none_key": None, "ok": "yes"})


def test_sanitize_converts_datetime_to_isoformat() -> None:
    dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    result = _sanitize_attrs({"ts": dt})
    assert isinstance(result["ts"], str)


def test_sanitize_converts_list_to_json() -> None:
    result = _sanitize_attrs({"items": ["a", "b", 3]})
    assert isinstance(result["items"], str)
    assert '"a"' in result["items"]


def test_sanitize_converts_dict_to_json() -> None:
    result = _sanitize_attrs({"nested": {"x": 1}})
    assert isinstance(result["nested"], str)


def test_sanitize_handles_empty_dict() -> None:
    assert _sanitize_attrs({}) == {}


# =============================================================================
# TraceConverter — _detect_format
# =============================================================================

def test_detect_format_returns_langchain_for_run_type() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"run_type": "chain", "child_runs": []}])
    assert fmt == c._convert_langchain_trace


def test_detect_format_returns_chat_for_messages() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"messages": []}])
    assert fmt == c._convert_chat_trace


def test_detect_format_returns_chat_for_conversation() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"conversation": []}])
    assert fmt == c._convert_chat_trace


def test_detect_format_returns_steps_for_steps() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"steps": []}])
    assert fmt == c._convert_steps_trace


def test_detect_format_returns_steps_for_actions() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"actions": []}])
    assert fmt == c._convert_steps_trace


def test_detect_format_returns_structured_for_spans() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"spans": []}])
    assert fmt == c._convert_structured_trace


def test_detect_format_returns_structured_for_traces() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"traces": []}])
    assert fmt == c._convert_structured_trace


def test_detect_format_returns_nested_list_for_list_field() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"events": [{"type": "a"}]}])
    assert fmt == c._convert_nested_list_trace


def test_detect_format_returns_generic_for_unknown() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"unknown_field": "value"}])
    assert fmt == c._convert_generic_json


def test_detect_format_returns_generic_for_empty_rows() -> None:
    c = TraceConverter()
    fmt = c._detect_format([])
    assert fmt == c._convert_generic_json


def test_detect_format_langchain_beats_chat() -> None:
    c = TraceConverter()
    fmt = c._detect_format([{"run_type": "chain", "child_runs": [], "messages": []}])
    assert fmt == c._convert_langchain_trace


# =============================================================================
# TraceConverter — _convert_langchain_trace
# =============================================================================

def test_convert_langchain_basic() -> None:
    c = TraceConverter()
    row = {
        "id": "run-001",
        "name": "my_chain",
        "run_type": "chain",
        "start_time": 1700000000,
        "end_time": 1700000100,
        "inputs": {"question": "hello"},
        "outputs": {"answer": "world"},
        "child_runs": [],
    }
    result = c._convert_langchain_trace(row)
    assert len(result) == 1
    root = result[0]
    assert root.span_id is not None
    assert len(root.span_id) > 0
    assert root.start_time is not None
    assert root.end_time is not None
    assert root.attributes is not None
    assert root.attributes.get("name") == "my_chain" or root.attributes.get("run_type") == "chain"


def test_convert_langchain_with_nested_children() -> None:
    c = TraceConverter()
    row = {
        "id": "run-001",
        "name": "parent",
        "run_type": "chain",
        "child_runs": [
            {
                "id": "run-002",
                "name": "child",
                "run_type": "tool",
                "child_runs": [],
            },
        ],
    }
    result = c._convert_langchain_trace(row)
    assert len(result) == 1
    root = result[0]
    assert len(root.child_spans) == 1
    assert root.child_spans[0].operation_name == "execute_tool"


def test_convert_langchain_tool_type_maps_to_execute_tool() -> None:
    c = TraceConverter()
    row = {
        "id": "run-001",
        "name": "tool_call",
        "run_type": "tool",
        "child_runs": [],
    }
    result = c._convert_langchain_trace(row)
    assert result[0].operation_name == "execute_tool"


def test_convert_langchain_handles_missing_id() -> None:
    c = TraceConverter()
    row = {
        "name": "trace",
        "run_type": "chain",
        "trace_id": "trace-999",
        "child_runs": [],
    }
    result = c._convert_langchain_trace(row)
    assert result[0].trace_id == "trace-999"


def test_convert_langchain_error_run_gets_error_status() -> None:
    c = TraceConverter()
    row = {
        "id": "run-err",
        "name": "failing",
        "run_type": "chain",
        "error": "something broke",
        "child_runs": [],
    }
    result = c._convert_langchain_trace(row)
    assert result[0].status == "error"


def test_convert_langchain_extra_metadata() -> None:
    c = TraceConverter()
    row = {
        "id": "run-001",
        "name": "traced",
        "run_type": "chain",
        "extra": {"custom": True},
        "metadata": {"pipeline": "prod"},
        "tags": ["test", "important"],
        "child_runs": [],
    }
    result = c._convert_langchain_trace(row)
    attrs = result[0].attributes or {}
    assert attrs.get("custom") is True


# =============================================================================
# TraceConverter — _convert_chat_trace
# =============================================================================

def test_convert_chat_with_messages() -> None:
    c = TraceConverter()
    row = {
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ],
    }
    result = c._convert_chat_trace(row)
    assert len(result) == 1
    root = result[0]
    assert root.operation_name == "invoke_agent"
    assert len(root.child_spans) == 2


def test_convert_chat_with_conversation_key() -> None:
    c = TraceConverter()
    row = {
        "conversation": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "help"},
        ],
    }
    result = c._convert_chat_trace(row)
    assert len(result[0].child_spans) == 2


def test_convert_chat_assigns_user_role_to_invoke_agent() -> None:
    c = TraceConverter()
    row = {"messages": [{"role": "user", "content": "q"}]}
    result = c._convert_chat_trace(row)
    assert result[0].child_spans[0].operation_name == "invoke_agent"


def test_convert_chat_truncates_long_content() -> None:
    c = TraceConverter()
    long_content = "x" * 600
    row = {"messages": [{"role": "assistant", "content": long_content}]}
    result = c._convert_chat_trace(row)
    attrs = result[0].child_spans[0].attributes or {}
    content = attrs.get("content", "")
    assert len(str(content)) <= 500


def test_convert_chat_skips_non_dict_messages() -> None:
    c = TraceConverter()
    row = {"messages": ["not-a-dict", {"role": "user", "content": "hi"}]}
    result = c._convert_chat_trace(row)
    assert len(result[0].child_spans) == 1


def test_convert_chat_with_missing_messages_falls_back() -> None:
    c = TraceConverter()
    row = {"other": "data"}
    result = c._convert_chat_trace(row)
    assert len(result) == 1
    assert result[0].operation_name == "invoke_agent"


# =============================================================================
# TraceConverter — _convert_steps_trace
# =============================================================================

def test_convert_steps_basic() -> None:
    c = TraceConverter()
    row = {
        "steps": [
            {"type": "tool_call", "name": "search", "timestamp": 1700000000},
            {"type": "think", "name": "decide"},
        ],
    }
    result = c._convert_steps_trace(row)
    root = result[0]
    assert root.operation_name == "invoke_agent"
    assert len(root.child_spans) == 2
    assert root.child_spans[0].operation_name == "execute_tool"
    assert root.child_spans[1].operation_name == "plan"


def test_convert_steps_with_actions_key() -> None:
    c = TraceConverter()
    row = {"actions": [{"type": "tool_call", "name": "lookup"}]}
    result = c._convert_steps_trace(row)
    assert len(result[0].child_spans) == 1


def test_convert_steps_with_turns_key() -> None:
    c = TraceConverter()
    row = {"turns": [{"type": "search", "query": "find"}]}
    result = c._convert_steps_trace(row)
    assert len(result[0].child_spans) == 1


def test_convert_steps_skips_non_dict_items() -> None:
    c = TraceConverter()
    row = {"steps": ["not-a-dict", {"type": "tool_call", "name": "valid"}]}
    result = c._convert_steps_trace(row)
    assert len(result[0].child_spans) == 1


def test_convert_steps_no_valid_key_falls_back() -> None:
    c = TraceConverter()
    row = {"random": "data"}
    result = c._convert_steps_trace(row)
    assert len(result) == 1


def test_convert_steps_excess_attributes() -> None:
    c = TraceConverter()
    row = {
        "steps": [
            {
                "type": "tool_call",
                "name": "custom",
                "query": "find-me",
                "result_count": 42,
            },
        ],
    }
    result = c._convert_steps_trace(row)
    span = result[0].child_spans[0]
    attrs = span.attributes or {}
    assert attrs.get("query") == "find-me"
    assert attrs.get("result_count") == 42


# =============================================================================
# TraceConverter — _convert_structured_trace
# =============================================================================

def test_convert_structured_basic() -> None:
    c = TraceConverter()
    row = {
        "spans": [
            {
                "span_id": "span-1",
                "trace_id": "trace-x",
                "operation_name": "invoke_agent",
                "start_time": 1700000000,
            },
            {
                "span_id": "span-2",
                "trace_id": "trace-x",
                "parent_span_id": "span-1",
                "operation_name": "execute_tool",
                "attributes": {"gen_ai.tool.name": "search"},
            },
        ],
    }
    result = c._convert_structured_trace(row)
    assert len(result) == 1
    root = result[0]
    assert root.span_id == "span-1"
    assert len(root.child_spans) == 1
    assert root.child_spans[0].span_id == "span-2"


def test_convert_structured_with_traces_key() -> None:
    c = TraceConverter()
    row = {
        "traces": [
            {
                "span_id": "s1",
                "trace_id": "t1",
                "operation_name": "plan",
            },
        ],
    }
    result = c._convert_structured_trace(row)
    assert len(result) == 1
    assert result[0].span_id == "s1"


def test_convert_structured_orphan_span_becomes_root() -> None:
    c = TraceConverter()
    row = {
        "spans": [
            {
                "span_id": "orphan",
                "trace_id": "tx",
                "parent_span_id": "nonexistent",
                "operation_name": "plan",
            },
        ],
    }
    result = c._convert_structured_trace(row)
    assert len(result) == 1
    assert result[0].span_id == "orphan"


def test_convert_structured_generates_trace_id_when_missing() -> None:
    c = TraceConverter()
    row = {
        "spans": [
            {"span_id": "s1", "operation_name": "plan"},
        ],
    }
    result = c._convert_structured_trace(row)
    assert result[0].trace_id


def test_convert_structured_empty_spans_falls_back() -> None:
    c = TraceConverter()
    row = {"spans": []}
    result = c._convert_structured_trace(row)
    assert len(result) >= 1


# =============================================================================
# TraceConverter — _convert_nested_list_trace
# =============================================================================

def test_convert_nested_list_detects_first_list_field() -> None:
    c = TraceConverter()
    row = {
        "trace_id": "t1",
        "operations": [
            {"type": "tool_call", "name": "step1"},
            {"type": "think", "name": "step2"},
        ],
    }
    result = c._convert_nested_list_trace(row)
    assert len(result) >= 1


def test_convert_nested_list_no_list_field_falls_back() -> None:
    c = TraceConverter()
    row = {"just": "text", "numbers": 42}
    result = c._convert_nested_list_trace(row)
    assert len(result) >= 1


# =============================================================================
# TraceConverter — _convert_generic_json
# =============================================================================

def test_convert_generic_basic() -> None:
    c = TraceConverter()
    row = {
        "name": "my-agent-run",
        "type": "invoke_agent",
        "start_time": "2024-01-15T10:00:00Z",
        "end_time": "2024-01-15T10:00:30Z",
        "status": "completed",
    }
    result = c._convert_generic_json(row)
    assert len(result) == 1
    root = result[0]
    assert root.operation_name == "invoke_agent"
    assert root.start_time is not None
    assert root.end_time is not None


def test_convert_generic_handles_error() -> None:
    c = TraceConverter()
    row = {"type": "tool_call", "error": "something failed"}
    result = c._convert_generic_json(row)
    assert result[0].status == "error"


def test_convert_generic_handles_error_message_key() -> None:
    c = TraceConverter()
    row = {"type": "search", "error_message": "timeout"}
    result = c._convert_generic_json(row)
    assert result[0].status == "error"


def test_convert_generic_missing_timestamps_defaults_now() -> None:
    c = TraceConverter()
    row = {"name": "search"}
    result = c._convert_generic_json(row)
    assert len(result) == 1
    assert result[0].start_time is not None


def test_convert_generic_finds_alternative_timing_keys() -> None:
    c = TraceConverter()
    row = {
        "type": "think",
        "created_at": 1700000000,
        "completed_at": 1700000100,
    }
    result = c._convert_generic_json(row)
    assert result[0].start_time is not None
    assert result[0].end_time is not None


def test_convert_generic_computes_duration() -> None:
    c = TraceConverter()
    row = {
        "type": "retrieval",
        "start_time": 1700000000,
        "end_time": 1700000005,
    }
    result = c._convert_generic_json(row)
    assert result[0].duration_ms == 5000


# =============================================================================
# TraceConverter — convert_batch
# =============================================================================

def test_convert_batch_processes_multiple_rows() -> None:
    c = TraceConverter()
    rows = [
        {"steps": [{"type": "tool_call", "name": "search"}]},
        {"steps": [{"type": "think", "name": "decide"}]},
    ]
    result = c.convert_batch("test-ds", rows)
    assert len(result) == 2
    assert len(result[0]) >= 1
    assert len(result[1]) >= 1


def test_convert_batch_handles_error_rows_gracefully() -> None:
    c = TraceConverter()
    rows = [
        {"steps": [{"type": "tool_call", "name": "search"}]},
        "not-a-dict",  # will fail silently
        {"steps": [{"type": "think", "name": "decide"}]},
    ]
    result = c.convert_batch("test-ds", rows)
    assert len(result) >= 2


# =============================================================================
# TraceConverter — validate_spans
# =============================================================================

def test_validate_spans_valid_tree_returns_empty() -> None:
    c = TraceConverter()
    root = SpanNode(
        span_id="root-1",
        trace_id="trace-1",
        operation_name="invoke_agent",
        child_spans=[
            SpanNode(
                span_id="child-1",
                trace_id="trace-1",
                parent_span_id="root-1",
                operation_name="plan",
                child_spans=[],
            ),
        ],
    )
    errors = c.validate_spans([root])
    assert errors == []


def test_validate_spans_detects_duplicate_span_id() -> None:
    c = TraceConverter()
    spans = [
        SpanNode(span_id="dup", trace_id="t1", operation_name="root", child_spans=[]),
        SpanNode(span_id="dup", trace_id="t2", operation_name="root2", child_spans=[]),
    ]
    errors = c.validate_spans(spans)
    assert len(errors) > 0
    assert any("Duplicate span_id" in e for e in errors)


def test_validate_spans_detects_missing_trace_id() -> None:
    c = TraceConverter()
    span = SpanNode(span_id="s1", trace_id="", operation_name="root", child_spans=[])
    errors = c.validate_spans([span])
    assert any("trace_id" in e.lower() for e in errors)


def test_validate_spans_detects_orphan_parent() -> None:
    c = TraceConverter()
    child = SpanNode(
        span_id="c1", trace_id="t1",
        parent_span_id="nonexistent",
        operation_name="plan", child_spans=[],
    )
    errors = c.validate_spans([child])
    assert len(errors) > 0


def test_validate_spans_detects_cycle() -> None:
    c = TraceConverter()
    s1 = SpanNode(span_id="r1", trace_id="t1", operation_name="root", child_spans=[])
    s2 = SpanNode(span_id="c1", trace_id="t1", parent_span_id="r1",
                  operation_name="plan", child_spans=[])
    s3 = SpanNode(span_id="r1", trace_id="t1", operation_name="root", child_spans=[])
    s1.child_spans = [s2]
    s2.child_spans = [s3]
    errors = c.validate_spans([s1])
    assert len(errors) > 0


def test_validate_spans_empty_list_is_valid() -> None:
    c = TraceConverter()
    errors = c.validate_spans([])
    assert errors == []


def test_validate_spans_single_node_is_valid() -> None:
    c = TraceConverter()
    root = SpanNode(span_id="r1", trace_id="t1", operation_name="root", child_spans=[])
    errors = c.validate_spans([root])
    assert errors == []


# =============================================================================
# TraceConverter — _convert_array_trace
# =============================================================================

def test_convert_array_delegates_to_steps() -> None:
    c = TraceConverter()
    row = {"items": [{"type": "think", "name": "decide"}]}
    result = c._convert_array_trace(row)
    assert len(result) >= 1