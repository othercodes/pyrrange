from __future__ import annotations

import pytest

from pyrrange._core import arrange, on_stage, step, then
from pyrrange.scene import Scene


@step
def create() -> str:
    return "resource"


@pytest.fixture
def torn_down() -> list[Scene]:
    return []


def _record_into(seen: list[Scene]):
    def teardown(scene: Scene) -> None:
        seen.append(scene)

    return teardown


def test_teardown_should_be_called_via_scene(torn_down: list[Scene]) -> None:
    scene = arrange(create(), teardown=_record_into(torn_down))

    assert torn_down == []
    scene.teardown()

    assert torn_down == [scene]


def test_teardown_should_access_labeled_results(torn_down: list[Scene]) -> None:
    scene = arrange(create(), teardown=_record_into(torn_down))

    scene.teardown()

    assert torn_down[0]["create"] == "resource"


def test_teardown_should_be_optional() -> None:
    scene = arrange(create())
    scene.teardown()


def test_teardown_should_see_then_steps(torn_down: list[Scene]) -> None:
    scene = arrange(
        create(),
        then("extra", lambda create=on_stage(): create + "_extra"),
        teardown=_record_into(torn_down),
    )

    scene.teardown()

    assert torn_down[0]["extra"] == "resource_extra"


def test_teardown_should_not_fire_without_an_explicit_call(torn_down: list[Scene]) -> None:
    arrange(create(), teardown=_record_into(torn_down))
    assert torn_down == []


def test_context_manager_should_call_teardown_on_exit(torn_down: list[Scene]) -> None:
    with arrange(create(), teardown=_record_into(torn_down)) as scene:
        assert scene["create"] == "resource"
        assert torn_down == []

    assert torn_down == [scene]


def test_context_manager_should_call_teardown_on_exception(torn_down: list[Scene]) -> None:
    with pytest.raises(RuntimeError):
        with arrange(create(), teardown=_record_into(torn_down)):
            raise RuntimeError("test crash")

    assert len(torn_down) == 1


def test_context_manager_should_not_suppress_exceptions(torn_down: list[Scene]) -> None:
    with pytest.raises(ValueError, match="propagate me"):
        with arrange(create(), teardown=_record_into(torn_down)):
            raise ValueError("propagate me")

    assert len(torn_down) == 1


def test_scene_should_support_contains_check() -> None:
    scene = arrange(create())
    assert "create" in scene
    assert "missing" not in scene


def test_scene_should_include_labels_in_repr() -> None:
    scene = arrange(create())
    assert "Context" in repr(scene)
    assert "create" in repr(scene)
