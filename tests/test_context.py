from __future__ import annotations

import copy

import pytest

from pyrrange._core import arrange, then
from pyrrange.context import Context


def test_registry_should_return_value_by_label() -> None:
    ctx = Context()
    ctx.set_result("register", "user_obj")
    assert ctx["register"] == "user_obj"


def test_registry_should_raise_key_error_when_label_missing() -> None:
    ctx = Context()
    with pytest.raises(KeyError, match="No step result for label 'missing'"):
        ctx["missing"]


def test_registry_should_show_available_labels_in_error() -> None:
    ctx = Context()
    ctx.set_result("register", "x")
    with pytest.raises(KeyError, match="register"):
        ctx["other"]


def test_registry_should_overwrite_when_same_label() -> None:
    ctx = Context()
    ctx.set_result("user", "first")
    ctx.set_result("user", "second")
    assert ctx["user"] == "second"


def test_registry_should_store_multiple_labels() -> None:
    ctx = Context()
    ctx.set_result("register", "user")
    ctx.set_result("plan", "plan_obj")
    assert ctx["register"] == "user"
    assert ctx["plan"] == "plan_obj"


def test_contains_should_return_true_when_label_present() -> None:
    ctx = Context()
    ctx.set_result("register", "user")
    assert "register" in ctx
    assert "missing" not in ctx


def test_repr_should_show_label_names() -> None:
    ctx = Context()
    ctx.set_result("register", "user")
    ctx.set_result("plan", "plan_obj")
    assert repr(ctx) == "Context(['register', 'plan'])"


def test_scene_should_survive_being_copied() -> None:
    # __getattr__ reaches _context; on a half-built copy that lookup used to re-enter
    # __getattr__ forever instead of failing.
    scene = arrange(then("x", lambda: "value"))

    assert copy.copy(scene)["x"] == "value"
    assert copy.deepcopy(scene)["x"] == "value"
