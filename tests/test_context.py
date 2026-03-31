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
        ctx.set_result("step1", "user_obj")
        assert ctx.result == "user_obj"

    def test_set_result_overwrites_previous(self) -> None:
        ctx = Context()
        ctx.set_result("step1", "first")
        ctx.set_result("step2", "second")
        assert ctx.result == "second"


class TestContextRegistry:
    def test_access_by_label(self) -> None:
        ctx = Context()
        ctx.set_result("register", "user_obj")
        assert ctx["register"] == "user_obj"

    def test_missing_label_raises_key_error(self) -> None:
        ctx = Context()
        with pytest.raises(KeyError, match="No step result for label 'missing'"):
            ctx["missing"]

    def test_missing_label_shows_available(self) -> None:
        ctx = Context()
        ctx.set_result("register", "x")
        with pytest.raises(KeyError, match="register"):
            ctx["other"]

    def test_same_label_overwrites(self) -> None:
        ctx = Context()
        ctx.set_result("user", "first")
        ctx.set_result("user", "second")
        assert ctx["user"] == "second"

    def test_multiple_labels(self) -> None:
        ctx = Context()
        ctx.set_result("register", "user")
        ctx.set_result("plan", "plan_obj")
        assert ctx["register"] == "user"
        assert ctx["plan"] == "plan_obj"

    def test_contains_check(self) -> None:
        ctx = Context()
        ctx.set_result("register", "user")
        assert "register" in ctx
        assert "missing" not in ctx

    def test_repr(self) -> None:
        ctx = Context()
        ctx.set_result("register", "user")
        ctx.set_result("plan", "plan_obj")
        assert repr(ctx) == "Context(['register', 'plan'])"
