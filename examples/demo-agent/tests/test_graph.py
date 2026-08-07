"""Tests for the request-triage demo agent graph.

= Test coverage
Each test locks down one behavior class of the deterministic agent:

1. **Healthy runs** (``test_normal_run_resolves_quickly``):
   Normal input (known account + KB hit) must converge within 3 steps with
   outcome "resolve" and status "ok".

2. **Loop runs** (``test_loop_run_does_not_converge``):
   Missing account input must never converge, hitting the MAX_STEPS cap and
   escalating with status "error".  The tool log must show repeated lookups
   and searches (at least 3 of each, covering MAX_STEPS total).

3. **High cost runs** (``test_high_cost_run_spins_on_search``):
   Open-ended intent must route every turn to ``search_kb``, burning
   MAX_STEPS searches then escalating.  Tool log must contain only
   "search_kb" entries.

4. **Evidence-gated resolution**
   (``test_missing_account_blocks_resolution_even_with_known_intent``):
   Even with a known KB intent ("reset password"), a missing account
   prevents resolution.  This validates that the resolution gate requires
   BOTH evidence gates (account_ok AND kb_hit) to be true.

5. **Cost scaling** (``test_estimated_cost_scales_with_steps``):
   The linear cost model means high-cost runs must have higher estimated
   cost than normal runs.  If this ever inverts, the cost model is broken.

6. **Seed integrity** (``test_all_seeds_are_valid_and_distinct``):
   All named scenarios produce distinct inputs covering the three expected
   scenario names.
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
# ``CompiledStateGraph[Input, Config, State, Output]`` where:
#   Input = TriageState (the input dict)
#   Config = None (no runnable config needed)
#   State = TriageState (the shared state)
#   Output = TriageState (the final state dict)
Graph = CompiledStateGraph[TriageState, None, TriageState, TriageState]


@pytest.fixture()
def graph() -> Graph:
    """A freshly compiled graph per test (compilation is cheap).

    Each test gets an isolated graph instance so there's no shared state
    between test cases.  The graph is compiled from the module-level definition
    which is stateless.
    """
    return build_graph()


def _run(graph: Graph, request_input: TriageState) -> dict[str, Any]:
    """Invoke the graph and narrow the result to a plain dict for assertions.

    ``graph.invoke()`` returns a ``TriageState`` (which is a TypedDict, thus
    a dict at runtime), but mypy sees it as the generic type.  ``cast()``
    narrows it to ``dict[str, Any]`` for ergonomic assertions.

    Args:
        graph: A compiled request-triage graph.
        request_input: The TriageState input dict (from seed builders).

    Returns:
        The final state dict after graph completion.
    """
    result = graph.invoke(request_input)
    return cast(dict[str, Any], result)


def test_normal_run_resolves_quickly(graph: Graph) -> None:
    """Validate that a healthy input produces a fast, successful resolution.

    The normal seed uses ``acc_100`` (known account) + ``"reset password"``
    (known KB entry).  This should converge in at most 3 steps: lookup_account,
    search_kb, resolve.
    """
    result = _run(graph, normal_request())
    assert result["outcome"] == "resolve"
    assert result["status"] == "ok"
    assert result["step"] <= 3


def test_loop_run_does_not_converge(graph: Graph) -> None:
    """Validate that a missing account triggers step-cap escalation.

    The loop seed uses ``acc_404`` (missing account) + ``"missing_account"``
    intent.  Every other turn is a lookup_account (which fails) alternating with
    search_kb (which misses).  The run never converges and hits MAX_STEPS+1
    (because the step counter increments before the cap check).

    Post-conditions:
        - Outcome is escalate (not resolve).
        - Status is error.
        - Step count equals MAX_STEPS + 1 (planner increments THEN checks cap).
        - Tool log has at least MAX_STEPS entries (one per planner turn).
        - Both tool types appear at least 3 times (enough to exercise both).
    """
    result = _run(graph, loop_request())
    assert result["outcome"] == "escalate"
    assert result["status"] == "error"
    assert result["step"] == MAX_STEPS + 1
    log = result["tool_log"]
    assert len(log) >= MAX_STEPS
    assert log.count("lookup_account") >= 3
    assert log.count("search_kb") >= 3


def test_high_cost_run_spins_on_search(graph: Graph) -> None:
    """Validate that open-ended intents produce a high-search-count escalation.

    The high_cost seed uses ``acc_200`` (known account) + ``"open_ended"``
    intent.  The planner routes every turn to search_kb (never lookup_account,
    because the intent is open_ended).  The KB has no "open_ended" entry, so
    every search misses.  The run hits MAX_STEPS then escalates.

    Post-conditions:
        - Outcome is escalate.
        - Step count equals MAX_STEPS + 1.
        - Tool log contains ONLY "search_kb" entries (no lookups at all).
        - Tool log length equals MAX_STEPS (one search per planner turn).
    """
    result = _run(graph, high_cost_request())
    assert result["outcome"] == "escalate"
    assert result["step"] == MAX_STEPS + 1
    log = result["tool_log"]
    assert set(log) == {"search_kb"}  # Only KB searches, no account lookups.
    assert len(log) == MAX_STEPS


def test_missing_account_blocks_resolution_even_with_known_intent(graph: Graph) -> None:
    """Validate the dual-gate resolution logic.

    Even with a known KB entry ("reset password"), a missing account (acc_404)
    prevents resolution because the gate in run_tool requires BOTH account_ok
    and kb_hit to be satisfied.

    This test copies the normal seed but overrides account_id to force the
    loop path, ensuring the resolution gate is genuinely evidence-driven,
    not intent-driven.
    """
    request_input = normal_request()
    # Override the account to a missing one while keeping the known intent.
    request_input["account_id"] = "acc_404"
    result = _run(graph, request_input)
    assert result["outcome"] == "escalate"
    assert result["status"] == "error"
    assert result["account_ok"] is False


def test_estimated_cost_scales_with_steps(graph: Graph) -> None:
    """Validate the linear cost model: more steps = higher cost.

    The cost model is ``step * PER_TURN_COST``.  Since high_cost runs have
    MAX_STEPS+1 turns and normal runs have ~2 turns, the cost difference
    should be strictly positive.  If this inverts, the cost model (or the
    graph's step counting) is broken.
    """
    normal = _run(graph, normal_request())
    expensive = _run(graph, high_cost_request())
    assert expensive["estimated_cost"] > normal["estimated_cost"]


def test_all_seeds_are_valid_and_distinct() -> None:
    """Validate seed matrix completeness.

    Ensures:
        - The three canonical scenario names are present.
        - Normal and loop seeds have different scenarios.
        - High cost seed has the expected open_ended intent.

    This guards against accidental seed misconfiguration that would produce
    duplicate or degenerate test fixtures.
    """
    requests = all_requests()
    assert set(requests) == {"normal", "loop", "high_cost"}
    assert requests["normal"].get("scenario") != requests["loop"].get("scenario")
    assert requests["high_cost"].get("intent") == "open_ended"
