from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, StepError, on_stage, step
from pyrrange.scene import Scene


class UserArrange(Arrange):
    @step("user")
    def register(self, email: str = "test@example.com"):
        return {"type": "user", "email": email, "verified": False}

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

    @step("receipt")
    def with_receipt(self, order):
        return {"order_total": order["total"]}


def test_step_should_return_self_for_chaining() -> None:
    chain = UserArrange()
    result = chain.register()
    assert result is chain


def test_step_should_preserve_args() -> None:
    scene = OrderArrange().create(50).arrange()
    assert scene.order["total"] == 50


def test_step_should_preserve_kwargs() -> None:
    scene = UserArrange().register(email="custom@test.com").arrange()
    assert scene.user["email"] == "custom@test.com"


def test_label_should_default_to_method_name() -> None:
    class SimpleArrange(Arrange):
        @step
        def do_thing(self):
            return "done"

    scene = SimpleArrange().do_thing().arrange()
    assert scene["do_thing"] == "done"


def test_label_should_use_custom_value_when_provided() -> None:
    scene = UserArrange().register().arrange()
    assert "user" in scene


def test_label_should_accept_keyword_argument() -> None:
    class KeywordArrange(Arrange):
        @step(label="custom")
        def do_thing(self):
            return "done"

    scene = KeywordArrange().do_thing().arrange()
    assert scene["custom"] == "done"


def test_labels_should_be_accessible_after_arrange() -> None:
    scene = OrderArrange().create().paid().with_receipt().arrange()
    assert scene["order"]["paid"] is True
    assert scene["receipt"]["order_total"] == 100


def test_label_should_overwrite_when_same() -> None:
    scene = UserArrange().register().verified().arrange()
    assert scene["user"]["verified"] is True


def test_step_should_inject_from_context_when_no_default() -> None:
    scene = UserArrange().register().verified().arrange()
    assert scene["user"]["verified"] is True
    assert scene["user"]["email"] == "test@example.com"


def test_step_should_not_inject_when_param_has_default() -> None:
    class SafeArrange(Arrange):
        @step("email")
        def create_email(self):
            return "from_context@example.com"

        @step("message")
        def send(self, email: str = "default@example.com"):
            return f"sent to {email}"

    scene = SafeArrange().create_email().send().arrange()
    assert scene["message"] == "sent to default@example.com"


def test_step_should_prefer_caller_kwargs_over_context() -> None:
    scene = UserArrange().register().verified(user={"verified": False, "email": "override"}).arrange()
    assert scene["user"]["verified"] is True
    assert scene["user"]["email"] == "override"


def test_step_should_inject_multiple_params_from_context() -> None:
    class MultiArrange(Arrange):
        @step("api_client")
        def create_client(self):
            return "client_obj"

        @step("token")
        def create_token(self):
            return "token_123"

        @step("result")
        def use_both(self, api_client, token):
            return f"{api_client}:{token}"

    scene = MultiArrange().create_client().create_token().use_both().arrange()
    assert scene["result"] == "client_obj:token_123"


def test_arrange_should_return_scene() -> None:
    scene = UserArrange().register().arrange()
    assert isinstance(scene, Scene)


def test_arrange_should_return_scene_when_chain_empty() -> None:
    scene = UserArrange().arrange()
    assert isinstance(scene, Scene)


def test_then_should_inject_from_context() -> None:
    scene = UserArrange().register().then("email", lambda user: user["email"]).arrange()
    assert scene["email"] == "test@example.com"


def test_then_should_not_inject_when_param_has_default() -> None:
    scene = Arrange().then("start", lambda value="hello": value).arrange()
    assert scene["start"] == "hello"


def test_then_should_chain_with_steps() -> None:
    scene = UserArrange().register().then("greeting", lambda user: f"hello {user['email']}").arrange()
    assert scene["user"]["email"] == "test@example.com"
    assert scene["greeting"] == "hello test@example.com"


def test_then_should_accept_named_function() -> None:
    def extract_email(user):
        return user["email"]

    scene = UserArrange().register().then("email", extract_email).arrange()
    assert scene["email"] == "test@example.com"


def test_then_should_pass_extra_args() -> None:
    def format_greeting(user, prefix):
        return f"{prefix} {user['email']}"

    scene = UserArrange().register().then("greeting", format_greeting, "Welcome").arrange()
    assert scene["greeting"] == "Welcome test@example.com"


def test_then_should_pass_extra_kwargs() -> None:
    def format_greeting(user, prefix="Hi"):
        return f"{prefix} {user['email']}"

    scene = UserArrange().register().then("greeting", format_greeting, prefix="Welcome").arrange()
    assert scene["greeting"] == "Welcome test@example.com"


def test_then_should_ignore_extra_positional_args() -> None:
    scene = UserArrange().register().then("email", lambda user: user["email"], "extra_ignored").arrange()
    assert scene["email"] == "test@example.com"


def test_then_should_return_self_for_chaining() -> None:
    chain = Arrange()
    result = chain.then("x", lambda: None)
    assert result is chain


def test_then_should_wrap_error_in_step_error() -> None:
    def bad_fn():
        raise ValueError("boom")

    with pytest.raises(StepError, match="'fail'") as exc_info:
        Arrange().then("fail", bad_fn).arrange()
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "boom"


def test_scene_should_support_attribute_access() -> None:
    scene = UserArrange().register().verified().arrange()
    assert scene.user["verified"] is True
    assert scene.user["email"] == "test@example.com"


def test_scene_attribute_access_should_raise_on_missing_label() -> None:
    scene = UserArrange().register().arrange()
    with pytest.raises(AttributeError, match="no label 'missing'"):
        _unused = scene.missing


def test_scene_should_support_both_dict_and_attribute_access() -> None:
    scene = OrderArrange().create().paid().with_receipt().arrange()
    assert scene["order"] == scene.order
    assert scene["receipt"] == scene.receipt


class _User:
    def __init__(self, email: str) -> None:
        self.email = email


class _ApiClient:
    def __init__(self, token: str) -> None:
        self.token = token


class TypedArrange(Arrange):
    class SceneType(Scene):
        user: _User
        api_client: _ApiClient

    @step("user")
    def register(self, email: str = "test@example.com"):
        return _User(email=email)

    @step("api_client")
    def with_client(self, user: _User):
        return _ApiClient(token=f"token-for-{user.email}")


def test_scene_type_should_be_used_when_declared() -> None:
    scene = TypedArrange().register().with_client().arrange()
    assert isinstance(scene, TypedArrange.SceneType)


def test_scene_type_values_should_be_typed_instances() -> None:
    scene = TypedArrange().register().with_client().arrange()
    assert isinstance(scene.user, _User)
    assert isinstance(scene.api_client, _ApiClient)
    assert scene.user.email == "test@example.com"
    assert scene.api_client.token == "token-for-test@example.com"


def test_scene_type_should_support_both_access_patterns() -> None:
    scene = TypedArrange().register().arrange()
    assert scene.user is scene["user"]
    assert isinstance(scene.user, _User)


def test_scene_type_should_not_be_required() -> None:
    scene = UserArrange().register().arrange()
    assert isinstance(scene, Scene)
    assert scene.user["email"] == "test@example.com"


def test_clone_should_return_fresh_instance() -> None:
    original = UserArrange().register().verified()
    cloned = original.clone()
    assert cloned is not original


def test_clone_should_preserve_recorded_steps() -> None:
    original = UserArrange().register().verified()
    cloned = original.clone()
    scene = cloned.arrange()
    assert scene.user["verified"] is True
    assert scene.user["email"] == "test@example.com"


def test_clone_should_have_empty_context() -> None:
    original = UserArrange().register()
    original.arrange()
    cloned = original.clone()
    scene = cloned.arrange()
    assert scene.user["email"] == "test@example.com"


def test_clone_should_not_share_steps_list() -> None:
    original = UserArrange().register()
    cloned = original.clone()
    original.verified()
    scene = cloned.arrange()
    assert scene.user["verified"] is False


def test_clone_should_preserve_subclass_type() -> None:
    original = TypedArrange().register().with_client()
    cloned = original.clone()
    assert type(cloned) is TypedArrange
    scene = cloned.arrange()
    assert isinstance(scene, TypedArrange.SceneType)


def test_clone_should_preserve_then_steps() -> None:
    original = UserArrange().register().then("email", lambda user: user["email"])
    cloned = original.clone()
    scene = cloned.arrange()
    assert scene["email"] == "test@example.com"


def test_clone_should_allow_multiple_independent_executions() -> None:
    template = UserArrange().register()
    scene_a = template.clone().arrange()
    scene_b = template.clone().arrange()
    assert scene_a.user is not scene_b.user
    assert scene_a.user["email"] == scene_b.user["email"]


class StagedArrange(Arrange):
    @step("user")
    def register(self, email: str = "test@example.com") -> dict:
        return {"email": email, "verified": False}

    @step("user")
    def verified(self, user: dict = on_stage()) -> dict:
        user["verified"] = True
        return user

    @step("token")
    def with_token(self, owner: dict = on_stage("user")) -> str:
        return f"token-{owner['email']}"


def test_on_stage_should_inject_by_parameter_name() -> None:
    scene = StagedArrange().register().verified().arrange()
    assert scene["user"]["verified"] is True


def test_on_stage_should_inject_by_explicit_label() -> None:
    # The label and the parameter deliberately differ: owner reads the "user" label.
    scene = StagedArrange().register().with_token().arrange()
    assert scene["token"] == "token-test@example.com"


def test_on_stage_should_prefer_caller_kwargs() -> None:
    scene = StagedArrange().register().verified(user={"email": "other", "verified": False}).arrange()
    assert scene["user"]["email"] == "other"


def test_on_stage_should_raise_when_label_is_missing() -> None:
    with pytest.raises(StepError) as exc_info:
        StagedArrange().verified().arrange()
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert "No step result for label 'user'" in str(exc_info.value.__cause__)


def test_on_stage_should_repr_for_debugging() -> None:
    assert repr(on_stage()) == "on_stage()"
    assert repr(on_stage("user")) == "on_stage('user')"


def test_steps_without_on_stage_should_still_inject() -> None:
    # The pre-on_stage style keeps working at runtime.
    scene = UserArrange().register().verified().arrange()
    assert scene["user"]["verified"] is True
