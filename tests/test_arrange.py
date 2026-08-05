from __future__ import annotations

import pytest

from pyrrange._core import StepError, arrange, on_stage, step, then
from pyrrange.scene import Scene


@step("user")
def register(email: str = "test@example.com"):
    return {"type": "user", "email": email, "verified": False}


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


@step("receipt")
def with_receipt(order: dict = on_stage()):
    return {"order_total": order["total"]}


def test_step_should_record_the_call_without_running_it() -> None:
    calls: list[str] = []

    @step("noisy")
    def noisy():
        calls.append("ran")

    record = noisy()

    assert calls == []
    arrange(record)
    assert calls == ["ran"]


def test_step_should_preserve_args() -> None:
    scene = arrange(create(50))
    assert scene.order["total"] == 50


def test_step_should_preserve_kwargs() -> None:
    scene = arrange(register(email="custom@test.com"))
    assert scene.user["email"] == "custom@test.com"


def test_label_should_default_to_function_name() -> None:
    @step
    def do_thing():
        return "done"

    scene = arrange(do_thing())

    assert scene["do_thing"] == "done"


def test_label_should_use_custom_value_when_provided() -> None:
    scene = arrange(register())
    assert "user" in scene


def test_label_should_accept_keyword_argument() -> None:
    @step(label="custom")
    def do_thing():
        return "done"

    scene = arrange(do_thing())

    assert scene["custom"] == "done"


def test_labels_should_be_accessible_after_arrange() -> None:
    scene = arrange(create(), paid(), with_receipt())
    assert scene["order"]["paid"] is True
    assert scene["receipt"]["order_total"] == 100


def test_label_should_overwrite_when_same() -> None:
    scene = arrange(register(), verified())
    assert scene["user"]["verified"] is True


def test_step_should_inject_from_the_scene_being_built() -> None:
    scene = arrange(register(), verified())
    assert scene["user"]["verified"] is True
    assert scene["user"]["email"] == "test@example.com"


def test_step_should_not_inject_when_param_has_a_plain_default() -> None:
    @step("email")
    def create_email():
        return "from_context@example.com"

    @step("message")
    def send(email: str = "default@example.com"):
        return f"sent to {email}"

    scene = arrange(create_email(), send())

    assert scene["message"] == "sent to default@example.com"


def test_step_should_prefer_caller_kwargs_over_the_scene() -> None:
    scene = arrange(register(), verified(user={"verified": False, "email": "override"}))
    assert scene["user"]["verified"] is True
    assert scene["user"]["email"] == "override"


def test_step_should_inject_multiple_params() -> None:
    @step("api_client")
    def create_client():
        return "client_obj"

    @step("token")
    def create_token():
        return "token_123"

    @step("result")
    def use_both(api_client: str = on_stage(), token: str = on_stage()):
        return f"{api_client}:{token}"

    scene = arrange(create_client(), create_token(), use_both())

    assert scene["result"] == "client_obj:token_123"


def test_arrange_should_return_scene() -> None:
    scene = arrange(register())
    assert isinstance(scene, Scene)


def test_arrange_should_return_scene_when_given_no_steps() -> None:
    scene = arrange()
    assert isinstance(scene, Scene)


def test_then_should_inject_from_the_scene_being_built() -> None:
    scene = arrange(register(), then("email", lambda user=on_stage(): user["email"]))
    assert scene["email"] == "test@example.com"


def test_then_should_not_inject_when_param_has_a_plain_default() -> None:
    scene = arrange(then("start", lambda value="hello": value))
    assert scene["start"] == "hello"


def test_then_should_compose_with_steps() -> None:
    scene = arrange(register(), then("greeting", lambda user=on_stage(): f"hello {user['email']}"))
    assert scene["user"]["email"] == "test@example.com"
    assert scene["greeting"] == "hello test@example.com"


def test_then_should_accept_a_named_function() -> None:
    def extract_email(user: dict = on_stage()):
        return user["email"]

    scene = arrange(register(), then("email", extract_email))

    assert scene["email"] == "test@example.com"


def test_then_should_pass_extra_args() -> None:
    def format_greeting(prefix, user: dict = on_stage()):
        return f"{prefix} {user['email']}"

    scene = arrange(register(), then("greeting", format_greeting, "Welcome"))

    assert scene["greeting"] == "Welcome test@example.com"


def test_then_should_pass_extra_kwargs() -> None:
    def format_greeting(user: dict = on_stage(), prefix: str = "Hi"):
        return f"{prefix} {user['email']}"

    scene = arrange(register(), then("greeting", format_greeting, prefix="Welcome"))

    assert scene["greeting"] == "Welcome test@example.com"


def test_then_should_ignore_extra_positional_args() -> None:
    scene = arrange(register(), then("email", lambda user=on_stage(): user["email"], "extra_ignored"))
    assert scene["email"] == "test@example.com"


def test_then_should_wrap_error_in_step_error() -> None:
    def bad_fn():
        raise ValueError("boom")

    with pytest.raises(StepError, match="'fail'") as exc_info:
        arrange(then("fail", bad_fn))
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "boom"


def test_scene_should_support_attribute_access() -> None:
    scene = arrange(register(), verified())
    assert scene.user["verified"] is True
    assert scene.user["email"] == "test@example.com"


def test_scene_attribute_access_should_raise_on_missing_label() -> None:
    scene = arrange(register())
    with pytest.raises(AttributeError, match="no label 'missing'"):
        _unused = scene.missing


def test_scene_should_support_both_dict_and_attribute_access() -> None:
    scene = arrange(create(), paid(), with_receipt())
    assert scene["order"] == scene.order
    assert scene["receipt"] == scene.receipt


class _User:
    def __init__(self, email: str) -> None:
        self.email = email


class _ApiClient:
    def __init__(self, token: str) -> None:
        self.token = token


class AccountScene(Scene):
    user: _User
    api_client: _ApiClient


@step("user")
def register_typed(email: str = "test@example.com"):
    return _User(email=email)


@step("api_client")
def with_client(user: _User = on_stage()):
    return _ApiClient(token=f"token-for-{user.email}")


def test_scene_should_use_the_declared_type() -> None:
    scene = arrange(register_typed(), with_client(), scene=AccountScene)
    assert isinstance(scene, AccountScene)


def test_declared_scene_values_should_be_typed_instances() -> None:
    scene = arrange(register_typed(), with_client(), scene=AccountScene)
    assert isinstance(scene.user, _User)
    assert isinstance(scene.api_client, _ApiClient)
    assert scene.user.email == "test@example.com"
    assert scene.api_client.token == "token-for-test@example.com"


def test_declared_scene_should_support_both_access_patterns() -> None:
    scene = arrange(register_typed(), scene=AccountScene)
    assert scene.user is scene["user"]
    assert isinstance(scene.user, _User)


def test_declared_scene_should_not_be_required() -> None:
    scene = arrange(register())
    assert isinstance(scene, Scene)
    assert scene.user["email"] == "test@example.com"


@step("token")
def with_token(owner: dict = on_stage("user")) -> str:
    return f"token-{owner['email']}"


def test_on_stage_should_inject_by_parameter_name() -> None:
    scene = arrange(register(), verified())
    assert scene["user"]["verified"] is True


def test_on_stage_should_inject_by_explicit_label() -> None:
    # The label and the parameter deliberately differ: owner reads the "user" label.
    scene = arrange(register(), with_token())
    assert scene["token"] == "token-test@example.com"


def test_on_stage_should_prefer_caller_kwargs() -> None:
    scene = arrange(register(), verified(user={"email": "other", "verified": False}))
    assert scene["user"]["email"] == "other"


def test_on_stage_should_raise_when_label_is_missing() -> None:
    with pytest.raises(StepError) as exc_info:
        arrange(verified())
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert "No step result for label 'user'" in str(exc_info.value.__cause__)


def test_on_stage_should_repr_for_debugging() -> None:
    assert repr(on_stage()) == "on_stage()"
    assert repr(on_stage("user")) == "on_stage('user')"


def test_step_without_on_stage_should_inject_by_name() -> None:
    # A parameter with no default at all is still injected, matching on its own name.
    @step("greeting")
    def greet(user):
        return f"hi {user['email']}"

    scene = arrange(register(), greet())

    assert scene["greeting"] == "hi test@example.com"
