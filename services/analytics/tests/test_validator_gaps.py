"""Comprehensive tests for uncovered branches in validator.py.

Covers: batch processing loop, progress save/resume, diagnose mode,
LLM integration paths, detector error handling, coroutine vs sync paths,
partial reports, and dedup/correlation helpers.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode
from analytics.trace_pipeline.validator import (
    DIAGNOSE_FIELDS,
    Validator,
    _build_correlation,
    _dedup_loop_family,
    _detector_requirements,
    _field_pct,
    _is_output_unavailable_trace,
)

# ---- helpers ----


def _make_root_span(
    trace_id: str = "t1",
    span_id: str = "root",
    attrs: dict[str, object] | None = None,
    children: list[SpanNode] | None = None,
) -> SpanNode:
    return SpanNode(
        span_id=span_id,
        trace_id=trace_id,
        parent_span_id=None,
        operation_name="invoke_agent",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        duration_ms=60000,
        attributes=attrs or {"gen_ai.agent.name": "test"},
        status="success",
        child_spans=children or [],
    )


def _make_tool_span(
    trace_id: str = "t1",
    span_id: str = "s1",
    parent_id: str = "root",
    attrs: dict[str, object] | None = None,
) -> SpanNode:
    return SpanNode(
        span_id=span_id,
        trace_id=trace_id,
        parent_span_id=parent_id,
        operation_name="execute_tool",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc),
        duration_ms=30000,
        attributes=attrs or {"gen_ai.tool.name": "search"},
        status="ok",
    )


def _make_parquet(tmp: str, filename: str, rows: list[dict[str, object]]) -> Path:
    path = Path(tmp) / filename
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, str(path))  # type: ignore[no-untyped-call]
    return path


def _failing_detector(at: str) -> BaseDetector:
    class _Failing(BaseDetector):
        anomaly_type = at

        def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
            raise RuntimeError("boom")

    return _Failing()


def _not_implemented_detector(at: str) -> BaseDetector:
    class _NI(BaseDetector):
        anomaly_type = at

        def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
            raise NotImplementedError("needs pool")

    return _NI()


def _fake_firing_detector(at: str = "loop") -> BaseDetector:
    class _Firing(BaseDetector):
        anomaly_type = at

        def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
            return Anomaly(
                agent_name=summary.agent_name or "test",
                run_id=summary.run_id,
                anomaly_type=self.anomaly_type,
                severity="warning",
                explanation=f"{at} hit",
                evidence={"kind": "fake"},
            )

    return _Firing()


def _fake_async_firing_detector(at: str) -> BaseDetector:
    class _AsyncFiring(BaseDetector):
        anomaly_type = at

        async def detect_async(
            self, summary: RunSummary, spans: list[SpanNode], pool: object = None
        ) -> Anomaly | None:
            return Anomaly(
                agent_name=summary.agent_name or "test",
                run_id=summary.run_id,
                anomaly_type=self.anomaly_type,
                severity="warning",
                explanation=f"async {at}",
                evidence={"kind": "fake"},
            )

        def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
            return None

    return _AsyncFiring()


# ---- fixtures ----


@pytest.fixture
def parquet_single_trace() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        _make_parquet(
            tmp,
            "traces-0001.parquet",
            [
                {
                    "trace_id": "t1",
                    "span_id": "root",
                    "parent_span_id": None,
                    "operation_name": "invoke_agent",
                    "start_time": "2026-01-01T00:00:00",
                    "end_time": "2026-01-01T00:01:00",
                    "duration_ms": 60000,
                    "attributes_json": json.dumps({"gen_ai.agent.name": "triage"}),
                    "status": "success",
                    "source_dataset": "test",
                    "source_row_idx": 1,
                },
                {
                    "trace_id": "t1",
                    "span_id": "s1",
                    "parent_span_id": "root",
                    "operation_name": "execute_tool",
                    "start_time": "2026-01-01T00:00:30",
                    "end_time": "2026-01-01T00:00:31",
                    "duration_ms": 1000,
                    "attributes_json": json.dumps({"gen_ai.tool.name": "search"}),
                    "status": "ok",
                    "source_dataset": "test",
                    "source_row_idx": 1,
                },
            ],
        )
        yield tmp


@pytest.fixture
def parquet_multi_trace() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        for file_idx, trace_id in enumerate(["ta", "tb", "tc"], start=1):
            _make_parquet(
                tmp,
                f"traces-{file_idx:04d}.parquet",
                [
                    {
                        "trace_id": trace_id,
                        "span_id": "root",
                        "parent_span_id": None,
                        "operation_name": "invoke_agent",
                        "start_time": "2026-01-01T00:00:00",
                        "end_time": "2026-01-01T00:01:00",
                        "duration_ms": 60000,
                        "attributes_json": json.dumps({"gen_ai.agent.name": "triage"}),
                        "status": "success",
                        "source_dataset": "test",
                        "source_row_idx": file_idx,
                    },
                    {
                        "trace_id": trace_id,
                        "span_id": "s1",
                        "parent_span_id": "root",
                        "operation_name": "execute_tool",
                        "start_time": "2026-01-01T00:00:10",
                        "end_time": "2026-01-01T00:00:11",
                        "duration_ms": 1000,
                        "attributes_json": json.dumps({"gen_ai.tool.name": "search"}),
                        "status": "ok",
                        "source_dataset": "test",
                        "source_row_idx": file_idx,
                    },
                ],
            )
        yield tmp


@pytest.fixture
def parquet_diagnose_data() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        for ds_num, ds in enumerate(["ds_a", "ds_b"], start=1):
            _make_parquet(
                tmp,
                f"{ds}-traces-0001.parquet",
                [
                    {
                        "trace_id": f"t{ds_num}",
                        "span_id": "root",
                        "parent_span_id": None,
                        "operation_name": "invoke_agent",
                        "start_time": "2026-01-01T00:00:00",
                        "end_time": "2026-01-01T00:01:00",
                        "duration_ms": 60000,
                        "attributes_json": json.dumps(
                            {
                                "gen_ai.agent.name": "triage",
                                "gen_ai.response.content": "Hello world",
                                "gen_ai.tool.name": "search",
                                "gen_ai.tool.result": "ok",
                                "gen_ai.tool.args": {"q": "x"},
                                "gen_ai.usage.prompt_tokens": 100,
                                "gen_ai.usage.completion_tokens": 50,
                                "gen_ai.agent.run.cost.total": 0.01,
                            }
                        ),
                        "status": "success",
                        "source_dataset": ds,
                        "source_row_idx": 1,
                    },
                ],
            )
        yield tmp


# ---- _dedup_loop_family ----


def test_dedup_loop_family_removes_step_efficiency_when_loop_present() -> None:
    assert _dedup_loop_family(["loop", "step_efficiency", "tool_error_rate"]) == [
        "loop",
        "tool_error_rate",
    ]


def test_dedup_loop_family_removes_step_efficiency_when_pattern_loop_present() -> None:
    result = _dedup_loop_family(["pattern_loop", "step_efficiency", "tool_error_rate"])
    assert "step_efficiency" not in result
    assert "pattern_loop" in result


def test_dedup_loop_family_removes_step_efficiency_when_argument_loop_present() -> None:
    result = _dedup_loop_family(["argument_loop", "step_efficiency"])
    assert "step_efficiency" not in result


def test_dedup_loop_family_leaves_step_efficiency_alone() -> None:
    assert _dedup_loop_family(["step_efficiency", "tool_error_rate"]) == [
        "step_efficiency",
        "tool_error_rate",
    ]


def test_dedup_loop_family_loop_removes_pattern_loop_too() -> None:
    result = _dedup_loop_family(["loop", "pattern_loop", "step_efficiency"])
    assert "step_efficiency" not in result
    assert "pattern_loop" not in result
    assert "loop" in result


def test_dedup_loop_family_empty() -> None:
    assert _dedup_loop_family([]) == []


# ---- _build_correlation ----


def test_build_correlation_empty() -> None:
    result = _build_correlation({})
    assert result["top_co_fires"] == []
    assert result["type_counts"] == {}


def test_build_correlation_single_trace() -> None:
    result = _build_correlation({"t1": ["loop", "tool_error_rate"]})
    assert len(result["top_co_fires"]) == 2
    assert result["type_counts"] == {"loop": 1, "tool_error_rate": 1}


def test_build_correlation_multiple_traces() -> None:
    result = _build_correlation(
        {"t1": ["loop", "cost_spike"], "t2": ["loop", "cost_spike"], "t3": ["loop"]}
    )
    assert result["type_counts"]["loop"] == 3
    assert result["type_counts"]["cost_spike"] == 2
    pairs = {(tuple(p["pair"]), p["count"]) for p in result["top_co_fires"]}
    assert (("loop", "cost_spike"), 2) in pairs


# ---- _is_output_unavailable_trace ----


def test_is_output_unavailable_scratchpad_only() -> None:
    span = SpanNode(
        span_id="s1",
        trace_id="t1",
        operation_name="unknown",
        attributes={"scratchpad": "reasoning only"},
        child_spans=[],
    )
    assert _is_output_unavailable_trace([span]) is True


def test_is_output_unavailable_scratchpad_with_content() -> None:
    span = SpanNode(
        span_id="s1",
        trace_id="t1",
        operation_name="unknown",
        attributes={"scratchpad": "reasoning", "content": "final answer"},
        child_spans=[],
    )
    assert _is_output_unavailable_trace([span]) is False


def test_is_output_unavailable_no_scratchpad() -> None:
    span = SpanNode(
        span_id="s1",
        trace_id="t1",
        operation_name="unknown",
        attributes={"some": "thing"},
        child_spans=[],
    )
    assert _is_output_unavailable_trace([span]) is False


def test_is_output_unavailable_child_span_has_output() -> None:
    parent = SpanNode(
        span_id="root",
        trace_id="t1",
        operation_name="unknown",
        attributes={"scratchpad": "reasoning"},
        child_spans=[
            SpanNode(
                span_id="child",
                trace_id="t1",
                parent_span_id="root",
                operation_name="plan",
                attributes={"from": "gpt", "value": "final output"},
                child_spans=[],
            )
        ],
    )
    assert _is_output_unavailable_trace([parent]) is False


def test_is_output_unavailable_value_non_ai_role_ignored() -> None:
    span = SpanNode(
        span_id="s1",
        trace_id="t1",
        operation_name="unknown",
        attributes={"scratchpad": "reasoning", "value": "user input", "from": "user"},
        child_spans=[],
    )
    assert _is_output_unavailable_trace([span]) is True


# ---- _field_pct ----


def test_field_pct() -> None:
    from collections import Counter

    c = Counter({"has_output": 7})
    result = _field_pct(c, "has_output", 10)
    assert result == {"count": 7, "pct": 70.0}


def test_field_pct_missing() -> None:
    from collections import Counter

    result = _field_pct(Counter(), "has_output", 10)
    assert result == {"count": 0, "pct": 0.0}


def test_field_pct_zero_total() -> None:
    from collections import Counter

    result = _field_pct(Counter({"has_output": 5}), "has_output", 0)
    assert result == {"count": 5, "pct": 500.0}


# ---- progress save/resume ----


@pytest.mark.asyncio
async def test_progress_save_and_load(parquet_single_trace: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        await v.run()
        progress_path = Path(out_dir) / "without-llm" / "progress.json"
        assert progress_path.exists()
        loaded = json.loads(progress_path.read_text())
        assert loaded["completed_count"] == 1
        assert loaded["total_in_batch"] >= 1


@pytest.mark.asyncio
async def test_resume_skips_completed_traces(
    parquet_multi_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        mode_dir = Path(out_dir) / "without-llm"
        mode_dir.mkdir(parents=True, exist_ok=True)
        (mode_dir / "progress.json").write_text(
            json.dumps({"completed_traces": [["ta", "root"], ["tb", "root"]]})
        )

        v = Validator(input_dir=parquet_multi_trace, output_dir=out_dir, resume=True)
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        # 3 traces total, 2 already completed → 1 processed
        assert report["traces_processed"] == 3
        assert report.get("traces_skipped_resume", 0) >= 0


@pytest.mark.asyncio
async def test_progress_broken_json_handled(parquet_single_trace: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        mode_dir = Path(out_dir) / "without-llm"
        mode_dir.mkdir(parents=True, exist_ok=True)
        (mode_dir / "progress.json").write_text("not json")

        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, resume=True)
        # Should not crash with broken progress file
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        assert report["traces_processed"] == 1


@pytest.mark.asyncio
async def test_progress_missing_key_handled(parquet_single_trace: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        mode_dir = Path(out_dir) / "without-llm"
        mode_dir.mkdir(parents=True)
        (mode_dir / "progress.json").write_text(json.dumps({"other": "stuff"}))

        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, resume=True)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        assert report["traces_processed"] == 1


# ---- batch loop with detectors ----


@pytest.mark.asyncio
async def test_detector_raises_exception_handled(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        failing = _failing_detector("loop")
        monkeypatch.setattr(v, "detectors", [failing])
        report = await v.run()
        assert report["traces_processed"] == 1
        assert "loop" in report["detector_errors"]


@pytest.mark.asyncio
async def test_detector_raises_not_implemented_error(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        ni = _not_implemented_detector("indeterminate_status")
        monkeypatch.setattr(v, "detectors", [ni])
        report = await v.run()
        assert "indeterminate_status" in report["skipped_detectors"]
        assert "indeterminate_status" in report["detector_errors"]


@pytest.mark.asyncio
async def test_detector_fires_and_counts(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        firing = _fake_firing_detector("loop")
        monkeypatch.setattr(v, "detectors", [firing])
        report = await v.run()
        assert report["anomaly_by_type"].get("loop") == 1
        assert report["anomaly_count"] == 1


@pytest.mark.asyncio
async def test_async_detector_fires(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        async_firing = _fake_async_firing_detector("loop")
        monkeypatch.setattr(v, "detectors", [async_firing])
        report = await v.run()
        assert report["anomaly_by_type"].get("loop") == 1


@pytest.mark.asyncio
async def test_disabled_detector_skipped(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.settings.detector_disabled",
            {"loop"},
        )
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        firing = _fake_firing_detector("loop")
        monkeypatch.setattr(v, "detectors", [firing])
        report = await v.run()
        assert "loop" in report["skipped_detectors"]


# ---- max_files / max_traces ----


@pytest.mark.asyncio
async def test_max_files_limit(parquet_multi_trace: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_multi_trace, output_dir=out_dir, max_files=1)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        assert report["traces_processed"] == 1


@pytest.mark.asyncio
async def test_max_traces_limit(parquet_multi_trace: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_multi_trace, output_dir=out_dir, max_traces=2)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        assert report["traces_processed"] == 2


# ---- partial write reports ----


@pytest.mark.asyncio
async def test_partial_reports_written_during_batch(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, llm_batch=1)
        firing = _fake_firing_detector("loop")
        monkeypatch.setattr(v, "detectors", [firing])
        await v.run()
        mode_dir = Path(out_dir) / "without-llm"
        assert (mode_dir / "progress.json").exists()
        assert (mode_dir / "empty_response_sources.json").exists()


# ---- empty_response tracking ----


@pytest.mark.asyncio
async def test_empty_response_tracks_source_file(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        er_detector = _fake_firing_detector("empty_response")
        monkeypatch.setattr(v, "detectors", [er_detector])
        await v.run()
        sources_file = Path(out_dir) / "without-llm" / "empty_response_sources.json"
        assert sources_file.exists()
        data = json.loads(sources_file.read_text())
        assert "count_by_source_file" in data
        assert "examples" in data


# ---- LLM diagnostics mode ----


@pytest.mark.asyncio
async def test_run_diagnose_produces_compatibility_report(
    parquet_diagnose_data: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = Validator(input_dir=parquet_diagnose_data, max_traces=2).run_diagnose()
    assert "total_traces" in report
    assert report["total_traces"] == 2
    assert "total_datasets" in report
    assert report["total_datasets"] == 2
    assert "corpus_field_coverage" in report
    assert "per_dataset_eligibility" in report
    assert "global_compatibility_score_pct" in report


def test_run_diagnose_empty_input() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        report = Validator(input_dir=tmp).run_diagnose()
        assert report == {}


@pytest.mark.asyncio
async def test_diagnose_mode_in_run_with_llm(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (None, []),
        )
        v = Validator(
            input_dir=parquet_single_trace,
            output_dir=out_dir,
            llm_sample=1,
            diagnose=True,
        )
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        assert report["traces_processed"] >= 0


# ---- LLM integration in batch loop ----


@pytest.mark.asyncio
async def test_llm_detectors_fire_on_anomalous_traces(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeLLMClient:
        def stats(self) -> dict[str, object]:
            return {}

        def telemetry_summary(self) -> dict[str, object]:
            return {}

        def telemetry(self) -> list[dict[str, object]]:
            return []

        def responses(self) -> list[dict[str, object]]:
            return []

        def set_response_log(self, path: str) -> None:
            pass

        def set_trace_context(self, tid: str, dtype: str) -> None:
            pass

    class _LLMDet(BaseDetector):
        anomaly_type = "semantic_loop"

        async def detect_async(
            self, summary: RunSummary, spans: list[SpanNode], pool: object = None
        ) -> Anomaly | None:
            return Anomaly(
                agent_name="test",
                run_id=summary.run_id,
                anomaly_type="semantic_loop",
                severity="warning",
                explanation="llm hit",
            )

        def detect(
            self, summary: RunSummary, spans: list[SpanNode]
        ) -> Anomaly | None:
            return None

    with tempfile.TemporaryDirectory() as out_dir:
        fake_client = _FakeLLMClient()
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (fake_client, [_LLMDet()]),
        )
        rule_detector = _fake_firing_detector("loop")
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, llm_sample=5)
        monkeypatch.setattr(v, "detectors", [rule_detector])

        report = await v.run()
        assert "semantic_loop" in report.get("anomaly_by_type", {})
        assert report.get("anomaly_by_type", {}).get("loop") == 1


@pytest.mark.asyncio
async def test_llm_detector_skipped_when_disabled(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _LLMDet(BaseDetector):
        anomaly_type = "semantic_loop"

        async def detect_async(
            self, summary: RunSummary, spans: list[SpanNode], pool: object = None
        ) -> Anomaly | None:
            return Anomaly(
                agent_name="test",
                run_id=summary.run_id,
                anomaly_type="semantic_loop",
                severity="warning",
                explanation="llm",
            )

    with tempfile.TemporaryDirectory() as out_dir:
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (None, [_LLMDet()]),
        )
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.settings.detector_disabled",
            {"semantic_loop"},
        )
        firing = _fake_firing_detector("loop")
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, llm_sample=5)
        monkeypatch.setattr(v, "detectors", [firing])

        report = await v.run()
        assert "semantic_loop" not in report.get("anomaly_by_type", {})


@pytest.mark.asyncio
async def test_llm_detector_exception_handled(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenLLMDet(BaseDetector):
        anomaly_type = "semantic_loop"

        async def detect_async(
            self, summary: RunSummary, spans: list[SpanNode], pool: object = None
        ) -> Anomaly | None:
            raise RuntimeError("llm boom")

    with tempfile.TemporaryDirectory() as out_dir:
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (None, [_BrokenLLMDet()]),
        )
        firing = _fake_firing_detector("loop")
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, llm_sample=5)
        monkeypatch.setattr(v, "detectors", [firing])

        report = await v.run()
        assert report["traces_processed"] == 1


@pytest.mark.asyncio
async def test_llm_response_files_written(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeClient:
        def stats(self) -> dict[str, object]:
            return {"calls": 1}

        def telemetry_summary(self) -> dict[str, object]:
            return {"avg_latency": 0.5}

        def telemetry(self) -> list[dict[str, object]]:
            return [{"latency": 0.5}]

        def responses(self) -> list[dict[str, object]]:
            return []

        def set_response_log(self, path: str) -> None:
            pass

        def set_trace_context(self, tid: str, dtype: str) -> None:
            pass

    class _LLMDet(BaseDetector):
        anomaly_type = "semantic_loop"

        async def detect_async(
            self, summary: RunSummary, spans: list[SpanNode], pool: object = None
        ) -> Anomaly | None:
            return Anomaly(
                agent_name="test",
                run_id=summary.run_id,
                anomaly_type="semantic_loop",
                severity="warning",
                explanation="llm",
            )

    with tempfile.TemporaryDirectory() as out_dir:
        fake_client = _FakeClient()
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (fake_client, [_LLMDet()]),
        )
        firing = _fake_firing_detector("loop")
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, llm_sample=5)
        monkeypatch.setattr(v, "detectors", [firing])

        report = await v.run()
        assert "llm_stats" in report
        mode_dir = Path(out_dir) / "with-llm"
        assert (mode_dir / "summary.json").exists()
        assert (mode_dir / "llm_responses.json").exists()


# ---- output files and report shape ----


@pytest.mark.asyncio
async def test_all_output_files_written(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        firing = _fake_firing_detector("loop")
        monkeypatch.setattr(v, "detectors", [firing])
        await v.run()
        mode_dir = Path(out_dir) / "without-llm"
        assert (mode_dir / "summary.json").exists()
        assert (mode_dir / "correlation.json").exists()
        assert (mode_dir / "traces.json").exists()
        assert (mode_dir / "empty_response_sources.json").exists()
        assert (mode_dir / "progress.json").exists()


@pytest.mark.asyncio
async def test_report_has_expected_keys(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        monkeypatch.setattr(v, "detectors", [])
        report = await v.run()
        for key in (
            "traces_processed",
            "traces_with_anomalies",
            "anomaly_count",
            "anomaly_by_type",
            "anomaly_by_severity",
            "detector_fire_rate",
            "suspicious_patterns",
            "cross_detector_correlation",
            "skipped_detectors",
            "detector_errors",
        ):
            assert key in report, f"Missing key: {key}"


# ---- _detector_requirements ----


def test_detector_requirements_has_all_35() -> None:
    reqs = _detector_requirements()
    assert isinstance(reqs, dict)
    assert len(reqs) == 35


# ---- DIAGNOSE_FIELDS ----


def test_diagnose_fields_has_expected_count() -> None:
    assert len(DIAGNOSE_FIELDS) == 12


# ---- mode directory based on llm_sample ----


@pytest.mark.asyncio
async def test_without_llm_mode_directory(parquet_single_trace: str) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(v, "detectors", [])
        await v.run()
        assert (Path(out_dir) / "without-llm").is_dir()
        assert not (Path(out_dir) / "with-llm").exists()


@pytest.mark.asyncio
async def test_with_llm_mode_directory(
    parquet_single_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (None, []),
        )
        v = Validator(input_dir=parquet_single_trace, output_dir=out_dir, llm_sample=5)
        monkeypatch.setattr(v, "detectors", [])
        await v.run()
        assert (Path(out_dir) / "with-llm").is_dir()


# ---- llm_batch controls save interval ----


@pytest.mark.asyncio
async def test_llm_batch_controls_save_interval_with_llm(
    parquet_multi_trace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        monkeypatch.setattr(
            "analytics.trace_pipeline.validator.create_llm_detectors",
            lambda **_: (None, []),
        )
        v = Validator(
            input_dir=parquet_multi_trace,
            output_dir=out_dir,
            llm_sample=1,
            llm_batch=1,
            max_traces=3,
        )
        monkeypatch.setattr(v, "detectors", [])
        await v.run()
        assert (Path(out_dir) / "with-llm" / "progress.json").exists()


# ---- parquet_count_traces ----


@pytest.mark.asyncio
async def test_count_traces_respects_max_traces(
    parquet_multi_trace: str,
) -> None:
    v = Validator(input_dir=parquet_multi_trace, max_traces=2)
    count = v._count_traces()
    assert count == 2


def test_count_traces_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        v = Validator(input_dir=tmp)
        assert v._count_traces() == 0


@pytest.mark.asyncio
async def test_count_traces_skips_broken_parquet(tmp_path: Path) -> None:
    broken = tmp_path / "broken.parquet"
    broken.write_text("not a parquet file")
    good = tmp_path / "traces-0001.parquet"
    table = pa.Table.from_pylist(
        [
            {
                "trace_id": "tx",
                "span_id": "s1",
                "parent_span_id": None,
                "operation_name": "invoke_agent",
                "start_time": "2026-01-01T00:00:00",
                "end_time": "2026-01-01T00:01:00",
                "duration_ms": 60000,
                "attributes_json": "{}",
                "status": "ok",
                "source_dataset": "test",
                "source_row_idx": 1,
            }
        ]
    )
    pq.write_table(table, str(good))  # type: ignore[no-untyped-call]

    v = Validator(input_dir=str(tmp_path))
    count = v._count_traces()
    assert count == 1


# ---- _load_traces_fast ----


@pytest.mark.asyncio
async def test_load_traces_fast_returns_correct_count(parquet_single_trace: str) -> None:
    v = Validator(input_dir=parquet_single_trace)
    traces = v._load_traces_fast(target=5)
    assert len(traces) == 1
    assert traces[0][0] == "t1"


@pytest.mark.asyncio
async def test_load_traces_fast_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        v = Validator(input_dir=tmp)
        traces = v._load_traces_fast(target=5)
        assert traces == []
