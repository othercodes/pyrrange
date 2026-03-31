from __future__ import annotations

import pytest

from pyrrange.context import Context


class TestContextDependencies:
    def test_set_and_get_dependency(self) -> None:
        ctx = Context()
        ctx.set("make_plan", lambda: "plan")
        assert ctx.get("make_plan")() == "plan"

    def test_get_missing_dependency_raises(self) -> None:
        ctx = Context()
        with pytest.raises(LookupError, match="Dependency 'missing' not found"):
            ctx.get("missing")

    def test_get_missing_shows_available(self) -> None:
        ctx = Context()
        ctx.set("make_plan", "x")
        with pytest.raises(LookupError, match="make_plan"):
            ctx.get("other")

    def test_has_returns_true_when_present(self) -> None:
        ctx = Context()
        ctx.set("db", "conn")
        assert ctx.has("db") is True

    def test_has_returns_false_when_absent(self) -> None:
        ctx = Context()
        assert ctx.has("db") is False

    def test_overwrite_dependency(self) -> None:
        ctx = Context()
        ctx.set("db", "old")
        ctx.set("db", "new")
        assert ctx.get("db") == "new"


class TestContextResult:
    def test_initial_result_is_none(self) -> None:
        ctx = Context()
        assert ctx.result is None

    def test_set_result_updates_result(self) -> None:
        ctx = Context()
        ctx.set_result("user_obj")
        assert ctx.result == "user_obj"

    def test_set_result_overwrites_previous(self) -> None:
        ctx = Context()
        ctx.set_result("first")
        ctx.set_result("second")
        assert ctx.result == "second"

    def test_results_tracks_all_values(self) -> None:
        ctx = Context()
        ctx.set_result("a")
        ctx.set_result("b")
        ctx.set_result("c")
        assert ctx.results == ["a", "b", "c"]

    def test_results_returns_copy(self) -> None:
        ctx = Context()
        ctx.set_result("a")
        results = ctx.results
        results.append("mutated")
        assert ctx.results == ["a"]
