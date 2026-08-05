"""Tests for the batch validator."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode
from analytics.trace_pipeline.validator import Validator


@pytest.fixture
def sample_parquet_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {
                "trace_id": "t1",
                "span_id": "root",
                "parent_span_id": None,
                "operation_name": "invoke_agent",
                "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00",
                "duration_ms": 60000,
                "attributes_json": json.dumps(
                    {"gen_ai.agent.name": "triage", "gen_ai.agent.version": "v1"}
                ),
                "status": "success",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
            {
                "trace_id": "t1",
                "span_id": "s1",
                "parent_span_id": "root",
                "operation_name": "execute_tool",
                "start_time": None,
                "end_time": None,
                "duration_ms": 100,
                "attributes_json": json.dumps({"gen_ai.tool.name": "search"}),
                "status": "ok",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
        ]
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(Path(tmp) / "traces-0001.parquet"))  # type: ignore[no-untyped-call]
        yield tmp


@pytest.mark.asyncio
async def test_validator_loads_and_runs_detectors(sample_parquet_dir: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=sample_parquet_dir, output_dir=out_dir)
        report = await v.run()
        assert report["traces_processed"] == 1
        assert "anomaly_by_type" in report
        assert "anomaly_count" in report
        assert "suspicious_patterns" in report
        assert "cross_detector_correlation" in report
        output_file = Path(out_dir) / "without-llm" / "empty_response_sources.json"
        assert output_file.exists()


@pytest.mark.asyncio
async def test_validator_empty_input() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        v = Validator(input_dir=tmp)
        report = await v.run()
        assert report["traces_processed"] == 0


@pytest.mark.asyncio
async def test_validator_llm_sample(sample_parquet_dir: str) -> None:
    v = Validator(input_dir=sample_parquet_dir, llm_sample=1)
    report = await v.run()
    assert report["traces_processed"] == 1


@pytest.mark.asyncio
async def test_validator_normalizes_hf_output_attributes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {
                "trace_id": "t2",
                "span_id": "root",
                "parent_span_id": None,
                "operation_name": "invoke_agent",
                "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00",
                "duration_ms": 60000,
                "attributes_json": json.dumps(
                    {
                        "gen_ai.agent.name": "triage",
                        "gen_ai.agent.version": "v1",
                        "assistant_response": (
                            "This is a non-empty assistant response "
                            "that should not look empty."
                        ),
                    }
                ),
                "status": "success",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
            {
                "trace_id": "t2",
                "span_id": "s1",
                "parent_span_id": "root",
                "operation_name": "execute_tool",
                "start_time": None,
                "end_time": None,
                "duration_ms": 100,
                "attributes_json": json.dumps(
                    {
                        "tool_name": "search",
                        "tool_output": "result-1",
                        "input_tokens": 12,
                        "output_tokens": 18,
                    }
                ),
                "status": "ok",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
        ]
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(Path(tmp) / "traces-0001.parquet"))  # type: ignore[no-untyped-call]

        v = Validator(input_dir=tmp)
        report = await v.run()

        anomaly_by_type = report["anomaly_by_type"]
        assert isinstance(anomaly_by_type, dict)
        assert "empty_response" not in anomaly_by_type


@pytest.mark.asyncio
async def test_validator_normalizes_from_value_chat_traces() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {
                "trace_id": "t3",
                "span_id": "root",
                "parent_span_id": None,
                "operation_name": "invoke_agent",
                "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00",
                "duration_ms": 60000,
                "attributes_json": json.dumps(
                    {
                        "gen_ai.agent.name": "triage",
                        "gen_ai.agent.version": "v1",
                    }
                ),
                "status": "success",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
            {
                "trace_id": "t3",
                "span_id": "s1",
                "parent_span_id": "root",
                "operation_name": "unknown",
                "start_time": None,
                "end_time": None,
                "duration_ms": 100,
                "attributes_json": json.dumps(
                    {
                        "from": "gpt",
                        "value": "This is the assistant's non-empty final answer.",
                    }
                ),
                "status": "ok",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
        ]
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(Path(tmp) / "traces-0001.parquet"))  # type: ignore[no-untyped-call]

        v = Validator(input_dir=tmp)
        report = await v.run()

        anomaly_by_type = report["anomaly_by_type"]
        assert isinstance(anomaly_by_type, dict)
        assert "empty_response" not in anomaly_by_type


@pytest.mark.asyncio
async def test_validator_parses_tool_response_blobs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tool_blob = (
            '<tool_response>\n'
            '{"tool_call_id":"functions.search_files:1","name":"search_files",'
            '"content":{"total_count":0}}\n'
            '</tool_response>'
        )
        rows = [
            {
                "trace_id": "t4",
                "span_id": "root",
                "parent_span_id": None,
                "operation_name": "invoke_agent",
                "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00",
                "duration_ms": 60000,
                "attributes_json": json.dumps(
                    {
                        "gen_ai.agent.name": "triage",
                        "gen_ai.agent.version": "v1",
                        "assistant_response": "Done.",
                    }
                ),
                "status": "success",
                "source_dataset": "test",
                "source_row_idx": 1,
            },
        ]
        for i, tname in enumerate(["search_files", "find_files", "list_files"]):
            rows.append(
                {
                    "trace_id": "t4",
                    "span_id": f"s{i}",
                    "parent_span_id": "root",
                    "operation_name": "unknown",
                    "start_time": None,
                    "end_time": None,
                    "duration_ms": 100,
                    "attributes_json": json.dumps({
                        "from": "tool",
                        "value": tool_blob.replace("search_files", tname),
                    }),
                    "status": "ok",
                    "source_dataset": "test",
                    "source_row_idx": 1,
                }
            )
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(Path(tmp) / "traces-0001.parquet"))  # type: ignore[no-untyped-call]

        v = Validator(input_dir=tmp)
        report = await v.run()

        anomaly_by_type = report["anomaly_by_type"]
        assert isinstance(anomaly_by_type, dict)
        assert anomaly_by_type.get("wasted_tool_calls") == 1


@pytest.mark.asyncio
async def test_validator_suppresses_empty_response_for_scratchpad_only_trace() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {
                "trace_id": "t5",
                "span_id": "root",
                "parent_span_id": None,
                "operation_name": "unknown",
                "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00",
                "duration_ms": 60000,
                "attributes_json": json.dumps(
                    {
                        "scratchpad": "Reasoning only, no final answer stored.",
                        "label": "honest",
                        "model_family": "qwen",
                    }
                ),
                "status": "success",
                "source_dataset": "test",
                "source_row_idx": 1,
            }
        ]
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(Path(tmp) / "traces-0001.parquet"))  # type: ignore[no-untyped-call]

        v = Validator(input_dir=tmp)
        report = await v.run()

        anomaly_by_type = report["anomaly_by_type"]
        assert isinstance(anomaly_by_type, dict)
        assert "empty_response" not in anomaly_by_type


class _FakeLLMDetector(BaseDetector):
    anomaly_type = "semantic_loop"

    async def detect_async(
        self, summary: RunSummary, spans: list[SpanNode], pool: object = None
    ) -> Anomaly | None:
        return Anomaly(
            agent_name=summary.agent_name,
            run_id=summary.run_id,
            anomaly_type=self.anomaly_type,
            severity="warning",
            explanation="fake llm hit",
            evidence={"kind": "fake"},
        )

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        return None


@pytest.mark.asyncio
async def test_validator_includes_llm_detectors_when_sample_enabled(
    sample_parquet_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "analytics.trace_pipeline.validator.create_llm_detectors",
        lambda: [_FakeLLMDetector()],
    )

    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=sample_parquet_dir, output_dir=out_dir, llm_sample=1)
        report = await v.run()
        anomaly_by_type = report["anomaly_by_type"]
        assert isinstance(anomaly_by_type, dict)
        assert anomaly_by_type.get("semantic_loop") == 1
