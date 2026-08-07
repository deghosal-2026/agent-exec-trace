"""Tests for PydanticAI v1/v2 compatibility adapter."""

from __future__ import annotations

import pytest

from agent_exec_trace import pydantic as pyd_mod
from agent_exec_trace.pydantic import (
    is_pydanticai_v1,
    is_pydanticai_v2,
    pydanticai_version,
    trace_pydantic_agent,
)


def test_pydanticai_version_returns_string_or_none() -> None:
    result = pydanticai_version()
    assert result is None or isinstance(result, str)


def test_v1_check_returns_bool() -> None:
    assert isinstance(is_pydanticai_v1(), bool)


def test_v2_check_returns_bool() -> None:
    assert isinstance(is_pydanticai_v2(), bool)


def test_v1_and_v2_are_mutually_exclusive() -> None:
    assert not (is_pydanticai_v1() and is_pydanticai_v2())


def test_trace_pydantic_agent_without_pydantic_raises_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", None)
    with pytest.raises(ImportError, match="not installed"):
        trace_pydantic_agent(None)


def test_trace_pydantic_agent_returns_agent_for_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", "2.0.1")
    dummy: dict[str, bool] = {"agent": True}
    result = trace_pydantic_agent(dummy)
    assert result is dummy


def test_trace_pydantic_agent_raises_for_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", "1.0.0")
    with pytest.raises(NotImplementedError, match="@trace_agent"):
        trace_pydantic_agent(None)


def test_trace_pydantic_agent_unknown_version_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", "99.0.0")
    dummy: dict[str, bool] = {"agent": True}
    result = trace_pydantic_agent(dummy)
    assert result is dummy


def test_version_not_none_when_pydantic_installed() -> None:
    import importlib.util

    spec = importlib.util.find_spec("pydantic_ai")
    if spec is None:
        assert pydanticai_version() is None
    else:
        assert pydanticai_version() is not None


def test_is_pydanticai_v1_with_mocked_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", "1.5.0")
    assert is_pydanticai_v1() is True
    assert is_pydanticai_v2() is False


def test_is_pydanticai_v2_with_mocked_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", "2.3.0")
    assert is_pydanticai_v2() is True
    assert is_pydanticai_v1() is False


def test_is_pydanticai_v1_none_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyd_mod, "_PYDANTICAI_VERSION", None)
    assert is_pydanticai_v1() is False
    assert is_pydanticai_v2() is False
