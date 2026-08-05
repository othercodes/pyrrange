from __future__ import annotations

import pytest

from pyrrange._core import on_stage, step
from pyrrange.pytest import scene_fixture
from pyrrange.scene import Scene


class UserScene(Scene):
    user: dict


@step("user")
def register(email: str = "test@example.com"):
    return {"email": email, "verified": False}


@step("user")
def verified(user: dict = on_stage()):
    user["verified"] = True
    return user


@step("order")
def create(total: int = 100):
    return {"total": total, "paid": False}


@step("order")
def paid(order: dict = on_stage()):
    order["paid"] = True
    return order


# -- scene_fixture tests --

registered = scene_fixture(register())
authenticated = scene_fixture(register(), verified())
typed = scene_fixture(register(), scene=UserScene)


def test_scene_fixture_should_return_scene(registered: Scene) -> None:
    assert isinstance(registered, Scene)


def test_scene_fixture_should_run_the_steps(registered: Scene) -> None:
    assert registered.user["email"] == "test@example.com"


def test_scene_fixture_should_isolate_between_tests(registered: Scene) -> None:
    registered.user["email"] = "mutated@example.com"
    # If isolation works, the next test using `registered` gets a fresh scene


def test_scene_fixture_should_not_leak_mutations(registered: Scene) -> None:
    assert registered.user["email"] == "test@example.com"


def test_scene_fixture_should_accept_several_steps(authenticated: Scene) -> None:
    assert authenticated.user["verified"] is True


def test_scene_fixture_should_use_the_declared_scene(typed: UserScene) -> None:
    assert isinstance(typed, UserScene)


# -- @pytest.mark.arrange tests --

_registered = (register(),)
_verified = (register(), verified())
_order = (create(), paid())


@pytest.mark.arrange(*_registered)
def test_marker_should_inject_scene_label(user) -> None:
    assert user["email"] == "test@example.com"


@pytest.mark.arrange(*_verified)
def test_marker_should_inject_every_step(user) -> None:
    assert user["verified"] is True


@pytest.mark.arrange(register(email="custom@test.com"))
def test_marker_should_support_steps_declared_inline(user) -> None:
    assert user["email"] == "custom@test.com"


@pytest.mark.arrange(*_order)
def test_marker_should_inject_multiple_labels(order) -> None:
    assert order["total"] == 100
    assert order["paid"] is True


@pytest.mark.arrange(*_registered)
def test_marker_should_coexist_with_fixtures(user, tmp_path) -> None:
    assert user["email"] == "test@example.com"
    assert tmp_path.is_dir()


@pytest.mark.arrange(*_registered)
def test_marker_should_isolate_between_tests(user) -> None:
    user["email"] = "mutated@example.com"


@pytest.mark.arrange(*_registered)
def test_marker_should_not_leak_mutations(user) -> None:
    assert user["email"] == "test@example.com"


_teardown_calls: list[str] = []


@step("item")
def create_item():
    return "created"


@pytest.mark.arrange(create_item(), teardown=lambda scene: _teardown_calls.append(scene["item"]))
def test_marker_should_call_teardown(item) -> None:
    assert item == "created"


def test_marker_teardown_should_have_been_called() -> None:
    assert "created" in _teardown_calls


_scene_fixture_teardown_calls: list[str] = []


@step("item")
def create_sf_item():
    return "sf_created"


sf_teardown = scene_fixture(
    create_sf_item(),
    teardown=lambda scene: _scene_fixture_teardown_calls.append(scene["item"]),
)


def test_scene_fixture_should_call_teardown(sf_teardown) -> None:
    assert sf_teardown["item"] == "sf_created"


def test_scene_fixture_teardown_should_have_been_called() -> None:
    assert "sf_created" in _scene_fixture_teardown_calls
