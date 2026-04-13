from __future__ import annotations

from typing import Any, Literal

import pytest

from pyrrange.arrange import Arrange
from pyrrange.scene import Scene

_Scope = Literal["session", "package", "module", "class", "function"]

_scene_key = pytest.StashKey[Scene]()


def scene_fixture(
    chain: Arrange,
    scope: _Scope = "function",
) -> Any:
    @pytest.fixture(scope=scope)
    def _fixture() -> Any:
        with chain.clone().arrange() as scene:
            yield scene

    return _fixture


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "arrange(chain): execute an arrange chain and inject scene labels as test params"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    marker = item.get_closest_marker("arrange")
    if marker is None:
        return

    chain: Arrange = marker.args[0]
    scene = chain.clone().arrange()
    item.stash[_scene_key] = scene

    for name in getattr(item, "fixturenames", []):
        if name in scene:
            item.funcargs[name] = scene[name]  # type: ignore[attr-defined]


def pytest_runtest_teardown(item: pytest.Item) -> None:
    scene = item.stash.get(_scene_key, None)
    if scene is not None:
        scene.teardown()
