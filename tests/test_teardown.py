from __future__ import annotations

from pyrrange._core import Arrange, step
from pyrrange.scene import Scene

_torn_down = False
_torn_down_scene = None


class TrackedArrange(Arrange):
    @step
    def create(self):
        return "resource"

    def teardown(self, scene: Scene) -> None:
        global _torn_down, _torn_down_scene
        _torn_down = True
        _torn_down_scene = scene


def _reset():
    global _torn_down, _torn_down_scene
    _torn_down = False
    _torn_down_scene = None


def test_teardown_should_be_called_via_scene() -> None:
    _reset()
    scene = TrackedArrange().create().arrange()
    assert not _torn_down
    scene.teardown()
    assert _torn_down


def test_teardown_should_receive_scene() -> None:
    _reset()
    scene = TrackedArrange().create().arrange()
    scene.teardown()
    assert _torn_down_scene is scene


def test_teardown_should_access_labeled_results() -> None:
    _reset()
    scene = TrackedArrange().create().arrange()
    scene.teardown()
    assert _torn_down_scene["create"] == "resource"


def test_teardown_should_be_noop_on_base_arrange() -> None:
    scene = Arrange().arrange()
    scene.teardown()


def test_teardown_should_work_with_then_steps() -> None:
    _reset()
    scene = TrackedArrange().create().then("extra", lambda create: create + "_extra").arrange()
    scene.teardown()
    assert _torn_down
    assert _torn_down_scene["extra"] == "resource_extra"


def test_teardown_should_not_fire_without_explicit_call() -> None:
    _reset()
    TrackedArrange().create().arrange()
    assert not _torn_down


def test_context_manager_should_call_teardown_on_exit() -> None:
    _reset()
    with TrackedArrange().create().arrange() as scene:
        assert scene["create"] == "resource"
        assert not _torn_down
    assert _torn_down


def test_context_manager_should_call_teardown_on_exception() -> None:
    _reset()
    try:
        with TrackedArrange().create().arrange():
            raise RuntimeError("test crash")
    except RuntimeError:
        pass
    assert _torn_down


def test_context_manager_should_not_suppress_exceptions() -> None:
    _reset()
    caught = False
    try:
        with TrackedArrange().create().arrange():
            raise ValueError("propagate me")
    except ValueError:
        caught = True
    assert caught
    assert _torn_down


def test_scene_should_support_contains_check() -> None:
    scene = TrackedArrange().create().arrange()
    assert "create" in scene
    assert "missing" not in scene


def test_scene_should_include_labels_in_repr() -> None:
    scene = TrackedArrange().create().arrange()
    assert "Context" in repr(scene)
    assert "create" in repr(scene)
