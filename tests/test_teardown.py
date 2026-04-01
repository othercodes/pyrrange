from __future__ import annotations

from pyrrange.arrange import Arrange, step
from pyrrange.scene import Scene


class TrackedArrange(Arrange):
    """Arrange that tracks whether teardown was called."""

    torn_down = False
    torn_down_scene = None

    @step
    def create(self, previous):
        return "resource"

    def teardown(self, scene: Scene) -> None:
        TrackedArrange.torn_down = True
        TrackedArrange.torn_down_scene = scene


class TestTeardown:
    def setup_method(self):
        TrackedArrange.torn_down = False
        TrackedArrange.torn_down_scene = None

    def test_teardown_called_via_scene(self) -> None:
        scene = TrackedArrange().create().arrange()
        assert not TrackedArrange.torn_down
        scene.teardown()
        assert TrackedArrange.torn_down

    def test_teardown_receives_scene(self) -> None:
        scene = TrackedArrange().create().arrange()
        scene.teardown()
        assert TrackedArrange.torn_down_scene is scene

    def test_teardown_can_access_labeled_results(self) -> None:
        scene = TrackedArrange().create().arrange()
        scene.teardown()
        assert TrackedArrange.torn_down_scene["create"] == "resource"

    def test_base_arrange_teardown_is_noop(self) -> None:
        scene = Arrange().arrange()
        scene.teardown()  # should not raise

    def test_teardown_with_then(self) -> None:
        scene = TrackedArrange().create().then("extra", lambda prev: prev + "_extra").arrange()
        scene.teardown()
        assert TrackedArrange.torn_down
        assert TrackedArrange.torn_down_scene["extra"] == "resource_extra"

    def test_teardown_not_called_without_explicit_call(self) -> None:
        TrackedArrange().create().arrange()
        assert not TrackedArrange.torn_down


class TestSceneAccess:
    def test_contains_check(self) -> None:
        scene = TrackedArrange().create().arrange()
        assert "create" in scene
        assert "missing" not in scene

    def test_repr(self) -> None:
        scene = TrackedArrange().create().arrange()
        assert "Context" in repr(scene)
        assert "create" in repr(scene)
