"""Tests for the request-triage demo agent graph.

Each test locks down one behavior class of the deterministic agent: healthy runs
converge quickly, loop runs never converge and hit the step cap, high-cost runs
burn turns on KB searches, and resolution is genuinely gated on tool evidence.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from langgraph.graph.state import CompiledStateGraph

from request_triage.graph import MAX_STEPS, TriageState, build_graph
from request_triage.seeds import (
    all_requests,
    high_cost_request,
    loop_request,
    normal_request,
)

# The graph's fully-parameterized LangGraph type. Aliased so the fixture and helpers
# don't repeat the verbose four-type argument everywhere.
Graph = CompiledStateGraph[TriageState, None, TriageState, TriageState]


@pytest.fixture()
def graph() -> Graph:
    """A freshly compiled graph per test (compilation is cheap)."""
    return build_graph()


def _run(graph: Graph, request_input: TriageState) -> dict[str, Any]:
    """Invoke the graph and narrow the result to a plain dict for assertions."""
    result = graph.invoke(request_input)
    return cast(dict[str, Any], result)


def test_normal_run_resolves_quickly(graph: Graph) -> None:
    # Healthy input: account known + KB hit -> resolves within a few steps.
    result = _run(graph, normal_request())
    assert result["outcome"] == "resolve"
    assert result["status"] == "ok"
    assert result["step"] <= 3


def test_loop_run_does_not_converge(graph: Graph) -> None:
    # Missing account: lookups keep failing, searches keep missing -> hits the step
    # cap and escalates. The tool log should show many repeated lookups/searches.
    result = _run(graph, loop_request())
    assert result["outcome"] == "escalate"
    assert result["status"] == "error"
    assert result["step"] == MAX_STEPS + 1
    log = result["tool_log"]
    assert len(log) >= MAX_STEPS
    assert log.count("lookup_account") >= 3
    assert log.count("search_kb") >= 3


def test_high_cost_run_spins_on_search(graph: Graph) -> None:
    # open_ended intent routes every turn to search_kb; with no resolving KB hit it
    # burns MAX_STEPS searches then escalates -> a clean, high-cost fixture.
    result = _run(graph, high_cost_request())
    assert result["outcome"] == "escalate"
    assert result["step"] == MAX_STEPS + 1
    log = result["tool_log"]
    assert set(log) == {"search_kb"}
    assert len(log) == MAX_STEPS


def test_missing_account_blocks_resolution_even_with_known_intent(graph: Graph) -> None:
    # Evidence-gated resolution: a known intent is NOT enough. With a missing
    # account the run cannot resolve even though the KB knows "reset password".
    request_input = normal_request()
    request_input["account_id"] = "acc_404"
    result = _run(graph, request_input)
    assert result["outcome"] == "escalate"
    assert result["status"] == "error"
    assert result["account_ok"] is False


def test_estimated_cost_scales_with_steps(graph: Graph) -> None:
    # The linear cost model means longer (higher-turn) runs cost more. If this ever
    # inverts, the cost model is broken.
    normal = _run(graph, normal_request())
    expensive = _run(graph, high_cost_request())
    assert expensive["estimated_cost"] > normal["estimated_cost"]


def test_all_seeds_are_valid_and_distinct() -> None:
    # Every named scenario produces a distinct input, so fixture generation across
    # the whole scenario matrix stays non-degenerate.
    requests = all_requests()
    assert set(requests) == {"normal", "loop", "high_cost"}
    assert requests["normal"].get("scenario") != requests["loop"].get("scenario")
    assert requests["high_cost"].get("intent") == "open_ended"