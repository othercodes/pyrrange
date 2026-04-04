from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, StepError, step
from pyrrange.scene import Scene


class CounterArrange(Arrange):
    @step
    def add(self, value: int = 1):
        current = self.context.result or 0
        return current + value

    @step
    def multiply(self, factor: int = 2):
        return self.context.result * factor

    @step
    def noop(self):
        return self.context.result


class UserArrange(Arrange):
    @step
    def register(self, email: str = "test@example.com"):
        return {"type": "user", "email": email, "verified": False}

    @step
    def verified(self, register):
        register["verified"] = True
        return register


def test_step_should_record_without_executing() -> None:
    chain = CounterArrange().add(5)
    assert len(chain._recorded_steps) == 1
    assert chain.context.result is None


def test_steps_should_record_in_order() -> None:
    chain = CounterArrange().add(5).multiply(3).noop()
    assert len(chain._recorded_steps) == 3


def test_step_should_return_self_for_chaining() -> None:
    chain = CounterArrange()
    result = chain.add(1)
    assert result is chain


def test_step_should_preserve_args() -> None:
    chain = CounterArrange().add(42)
    assert chain._recorded_steps[0].args == (42,)


def test_step_should_preserve_kwargs() -> None:
    chain = CounterArrange().add(value=42)
    assert chain._recorded_steps[0].kwargs == {"value": 42}


def test_chain_should_have_no_steps_when_empty() -> None:
    chain = CounterArrange()
    assert len(chain._recorded_steps) == 0


def test_label_should_default_to_method_name() -> None:
    chain = CounterArrange().add(5)
    assert chain._recorded_steps[0].label == "add"


def test_label_should_use_custom_value_when_provided() -> None:
    class LabelArrange(Arrange):
        @step("custom")
        def do_thing(self):
            return "done"

    chain = LabelArrange().do_thing()
    assert chain._recorded_steps[0].label == "custom"


def test_label_should_accept_keyword_argument() -> None:
    class KeywordArrange(Arrange):
        @step(label="custom")
        def do_thing(self):
            return "done"

    scene = KeywordArrange().do_thing().arrange()
    assert scene["custom"] == "done"


def test_labels_should_be_accessible_after_arrange() -> None:
    scene = CounterArrange().add(5).multiply(3).arrange()
    assert scene["add"] == 5
    assert scene["multiply"] == 15


def test_label_should_overwrite_when_same() -> None:
    scene = UserArrange().register().verified().arrange()
    assert scene["register"]["verified"] is True
    assert scene["verified"]["verified"] is True


def test_step_should_inject_from_context_when_no_default() -> None:
    class InjectedArrange(Arrange):
        @step("user")
        def create_user(self, name: str = "Alice"):
            return {"name": name}

        @step("greeting")
        def greet(self, user):
            return f"Hello, {user['name']}!"

    scene = InjectedArrange().create_user().greet().arrange()
    assert scene["greeting"] == "Hello, Alice!"


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
    class OverrideArrange(Arrange):
        @step("user")
        def create_user(self):
            return {"name": "Context User"}

        @step("greeting")
        def greet(self, user):
            return f"Hello, {user['name']}!"

    scene = OverrideArrange().create_user().greet(user={"name": "Override"}).arrange()
    assert scene["greeting"] == "Hello, Override!"


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


def test_arrange_should_run_steps_in_order() -> None:
    scene = CounterArrange().add(5).multiply(3).arrange()
    assert scene.result == 15


def test_arrange_should_return_scene() -> None:
    scene = CounterArrange().add(5).arrange()
    assert isinstance(scene, Scene)


def test_scene_result_should_be_last_step() -> None:
    scene = CounterArrange().add(5).multiply(3).arrange()
    assert scene.result == 15


def test_arrange_should_return_scene_when_chain_empty() -> None:
    scene = CounterArrange().arrange()
    assert isinstance(scene, Scene)
    assert scene.result is None


def test_noop_should_preserve_result() -> None:
    scene = CounterArrange().add(7).noop().arrange()
    assert scene.result == 7


def test_first_step_should_not_inject_when_no_context() -> None:
    class CheckArrange(Arrange):
        @step
        def check(self, value: str = "default"):
            return value

    scene = CheckArrange().check().arrange()
    assert scene["check"] == "default"


def test_second_step_should_receive_injected_value() -> None:
    class CheckArrange(Arrange):
        @step("first")
        def create(self):
            return "hello"

        @step("second")
        def transform(self, first):
            return first.upper()

    scene = CheckArrange().create().transform().arrange()
    assert scene["second"] == "HELLO"


def test_then_should_inject_from_context() -> None:
    scene = CounterArrange().add(5).then("doubled", lambda add: add * 2).arrange()
    assert scene["doubled"] == 10


def test_then_should_not_inject_when_param_has_default() -> None:
    scene = Arrange().then("start", lambda value="hello": value).arrange()
    assert scene["start"] == "hello"


def test_then_should_chain_with_steps() -> None:
    scene = CounterArrange().add(10).then("formatted", lambda add: f"value={add}").arrange()
    assert scene["add"] == 10
    assert scene["formatted"] == "value=10"


def test_then_should_accept_named_function() -> None:
    def double_it(add):
        return add * 2

    scene = CounterArrange().add(5).then("doubled", double_it).arrange()
    assert scene["doubled"] == 10


def test_then_should_pass_extra_args() -> None:
    def multiply(add, factor):
        return add * factor

    scene = CounterArrange().add(5).then("result", multiply, 3).arrange()
    assert scene["result"] == 15


def test_then_should_pass_extra_kwargs() -> None:
    def multiply(add, factor=2):
        return add * factor

    scene = CounterArrange().add(5).then("result", multiply, factor=4).arrange()
    assert scene["result"] == 20


def test_then_should_return_self_for_chaining() -> None:
    chain = Arrange()
    result = chain.then("x", lambda: None)
    assert result is chain


def test_then_should_ignore_extra_positional_args() -> None:
    scene = CounterArrange().add(5).then("result", lambda add: add * 2, "extra_ignored").arrange()
    assert scene["result"] == 10


def test_then_should_wrap_error_in_step_error() -> None:
    def bad_fn():
        raise ValueError("boom")

    with pytest.raises(StepError, match="'fail'") as exc_info:
        Arrange().then("fail", bad_fn).arrange()
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "boom"


def test_then_should_create_derived_entity_from_context() -> None:
    def create_client(register):
        return {"type": "client", "token": f"token-for-{register['email']}"}

    scene = UserArrange().register(email="test@example.com").verified().then("api_client", create_client).arrange()
    assert scene["api_client"]["token"] == "token-for-test@example.com"
    assert scene["verified"]["verified"] is True
