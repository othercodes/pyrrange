from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, step
from pyrrange.pytest import scene_fixture
from pyrrange.scene import Scene


class UserArrange(Arrange):
    class SceneType(Scene):
        user: dict

    @step("user")
    def register(self, email: str = "test@example.com"):
        return {"email": email, "verified": False}

    @step("user")
    def verified(self, user):
        user["verified"] = True
        return user


class OrderArrange(Arrange):
    @step("order")
    def create(self, total: int = 100):
        return {"total": total, "paid": False}

    @step("order")
    def paid(self, order):
        order["paid"] = True
        return order


# -- scene_fixture tests --

registered = scene_fixture(UserArrange().register())
authenticated = scene_fixture(UserArrange().register().verified())


def test_scene_fixture_should_return_scene(registered: Scene) -> None:
    assert isinstance(registered, Scene)


def test_scene_fixture_should_execute_chain(registered: Scene) -> None:
    assert registered.user["email"] == "test@example.com"


def test_scene_fixture_should_isolate_between_tests(registered: Scene) -> None:
    registered.user["email"] = "mutated@example.com"
    # If isolation works, the next test using `registered` gets a fresh scene


def test_scene_fixture_should_not_leak_mutations(registered: Scene) -> None:
    assert registered.user["email"] == "test@example.com"


def test_scene_fixture_should_support_full_chain(authenticated: Scene) -> None:
    assert authenticated.user["verified"] is True


def test_scene_fixture_should_use_scene_type_when_declared(registered: UserArrange.SceneType) -> None:
    assert isinstance(registered, UserArrange.SceneType)


# -- @pytest.mark.arrange tests --

_registered = UserArrange().register()
_verified = UserArrange().register().verified()
_order = OrderArrange().create().paid()


@pytest.mark.arrange(_registered)
def test_marker_should_inject_scene_label(user) -> None:
    assert user["email"] == "test@example.com"


@pytest.mark.arrange(_verified)
def test_marker_should_inject_full_chain(user) -> None:
    assert user["verified"] is True


@pytest.mark.arrange(UserArrange().register(email="custom@test.com"))
def test_marker_should_support_inline_chain(user) -> None:
    assert user["email"] == "custom@test.com"


@pytest.mark.arrange(_order)
def test_marker_should_inject_multiple_labels(order) -> None:
    assert order["total"] == 100
    assert order["paid"] is True


@pytest.mark.arrange(_registered)
def test_marker_should_coexist_with_fixtures(user, tmp_path) -> None:
    assert user["email"] == "test@example.com"
    assert tmp_path.is_dir()


@pytest.mark.arrange(_registered)
def test_marker_should_isolate_between_tests(user) -> None:
    user["email"] = "mutated@example.com"


@pytest.mark.arrange(_registered)
def test_marker_should_not_leak_mutations(user) -> None:
    assert user["email"] == "test@example.com"


_teardown_calls: list[str] = []


class TeardownArrange(Arrange):
    @step("item")
    def create(self):
        return "created"

    def teardown(self, scene):
        _teardown_calls.append(scene["item"])


_teardown_chain = TeardownArrange().create()


@pytest.mark.arrange(_teardown_chain)
def test_marker_should_call_teardown(item) -> None:
    assert item == "created"


def test_marker_teardown_should_have_been_called() -> None:
    assert "created" in _teardown_calls


_scene_fixture_teardown_calls: list[str] = []


class SceneFixtureTeardownArrange(Arrange):
    @step("item")
    def create(self):
        return "sf_created"

    def teardown(self, scene):
        _scene_fixture_teardown_calls.append(scene["item"])


sf_teardown = scene_fixture(SceneFixtureTeardownArrange().create())


def test_scene_fixture_should_call_teardown(sf_teardown) -> None:
    assert sf_teardown["item"] == "sf_created"


def test_scene_fixture_teardown_should_have_been_called() -> None:
    assert "sf_created" in _scene_fixture_teardown_calls
