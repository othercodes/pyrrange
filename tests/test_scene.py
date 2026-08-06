from __future__ import annotations

import copy

import pytest

from pyrrange._core import arrange, step, then


@step("register")
def register() -> str:
    return "user_obj"


def test_scene_should_return_value_by_label() -> None:
    assert arrange(register())["register"] == "user_obj"


def test_scene_should_raise_key_error_when_label_missing() -> None:
    scene = arrange(register())
    with pytest.raises(KeyError, match="No step result for label 'missing'"):
        scene["missing"]


def test_scene_should_list_available_labels_in_the_error() -> None:
    scene = arrange(register())
    with pytest.raises(KeyError, match="register"):
        scene["other"]


def test_scene_should_survive_being_copied() -> None:
    # __getattr__ reaches _results; on a half-built copy that lookup used to re-enter
    # __getattr__ forever instead of failing.
    scene = arrange(then("x", lambda: "value"))

    assert copy.copy(scene)["x"] == "value"
    assert copy.deepcopy(scene)["x"] == "value"
