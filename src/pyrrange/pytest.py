from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any, Literal

import pytest

from pyrrange._core import Record, arrange
from pyrrange.scene import Scene

_Scope = Literal["session", "package", "module", "class", "function"]

_scene_key = pytest.StashKey[Scene]()


class ArrangeShadowWarning(UserWarning):
    """An arrange label took precedence over a pytest fixture of the same name."""


def scene_fixture(
    *records: Record,
    scope: _Scope = "function",
    scene: type[Scene] = Scene,
    teardown: Callable[[Scene], None] | None = None,
) -> Any:
    """Build a pytest fixture that arranges the given steps and tears them down afterwards.

    Scopes wider than ``"function"`` share one scene across tests and run teardown when
    the scope closes — long after a per-test DB transaction has been rolled back. Only
    widen the scope for state that outlives a transaction.
    """

    @pytest.fixture(scope=scope)
    def _fixture() -> Any:
        with arrange(*records, scene=scene, teardown=teardown) as built:
            yield built

    return _fixture


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "arrange(*steps, scene=..., teardown=...): run steps and inject scene labels as test params"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    marker = item.get_closest_marker("arrange")
    if marker is None:
        return

    scene = arrange(*marker.args, **marker.kwargs)
    item.stash[_scene_key] = scene

    # tryfirst: filling funcargs before pytest resolves fixtures is what lets a scene
    # label satisfy a test parameter that has no fixture behind it at all. The flip side
    # is that a real fixture of the same name never runs, so say so.
    fixtureinfo = getattr(item, "_fixtureinfo", None)
    defined_fixtures = getattr(fixtureinfo, "name2fixturedefs", {})

    for name in getattr(item, "fixturenames", []):
        if name not in scene:
            continue
        if name in defined_fixtures:
            warnings.warn(
                f"arrange label '{name}' shadows the fixture of the same name; the arrange value wins",
                ArrangeShadowWarning,
                stacklevel=1,
            )
        item.funcargs[name] = scene[name]  # type: ignore[attr-defined]


def pytest_runtest_teardown(item: pytest.Item) -> None:
    scene = item.stash.get(_scene_key, None)
    if scene is not None:
        scene.teardown()
