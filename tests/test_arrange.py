from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, StepError, step
from pyrrange.scene import Scene


class CounterArrange(Arrange):
    @step
    def add(self, previous, value: int = 1):
        current = previous or 0
        return current + value

    @step
    def multiply(self, previous, factor: int = 2):
        return previous * factor

    @step
    def noop(self, previous):
        return previous


class UserArrange(Arrange):
    @step
    def register(self, previous, email: str = "test@example.com"):
        return {"type": "user", "email": email, "verified": False}

    @step
    def verified(self, user):
        user["verified"] = True
        return user


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
        def do_thing(self, previous):
            return "done"

    chain = LabelArrange().do_thing()
    assert chain._recorded_steps[0].label == "custom"


def test_label_should_accept_keyword_argument() -> None:
    class KeywordArrange(Arrange):
        @step(label="custom")
        def do_thing(self, previous):
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


def test_step_should_access_sibling_label_via_context() -> None:
    class SiblingArrange(Arrange):
        @step("first")
        def step_one(self, previous):
            return "hello"

        @step("second")
        def step_two(self, previous):
            first_result = self.context["first"]
            return f"{first_result} world"

    scene = SiblingArrange().step_one().step_two().arrange()
    assert scene["second"] == "hello world"


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


def test_first_step_should_receive_none() -> None:
    class CheckArrange(Arrange):
        @step
        def check(self, previous):
            assert previous is None
            return "ok"

    scene = CheckArrange().check().arrange()
    assert scene["check"] == "ok"


def test_second_step_should_receive_first_result() -> None:
    class CheckArrange(Arrange):
        @step
        def first(self, previous):
            return "hello"

        @step
        def second(self, previous):
            return previous.upper()

    scene = CheckArrange().first().second().arrange()
    assert scene["second"] == "HELLO"


def test_then_should_receive_previous_result() -> None:
    scene = CounterArrange().add(5).then("doubled", lambda x: x * 2).arrange()
    assert scene["doubled"] == 10


def test_then_should_handle_none_previous() -> None:
    scene = Arrange().then("start", lambda prev: "hello").arrange()
    assert scene["start"] == "hello"


def test_then_should_chain_with_steps() -> None:
    scene = CounterArrange().add(10).then("formatted", lambda n: f"value={n}").arrange()
    assert scene["add"] == 10
    assert scene["formatted"] == "value=10"


def test_then_should_accept_named_function() -> None:
    def double_it(previous):
        return previous * 2

    scene = CounterArrange().add(5).then("doubled", double_it).arrange()
    assert scene["doubled"] == 10


def test_then_should_pass_extra_args() -> None:
    def multiply(previous, factor):
        return previous * factor

    scene = CounterArrange().add(5).then("result", multiply, 3).arrange()
    assert scene["result"] == 15


def test_then_should_pass_extra_kwargs() -> None:
    def multiply(previous, factor=2):
        return previous * factor

    scene = CounterArrange().add(5).then("result", multiply, factor=4).arrange()
    assert scene["result"] == 20


def test_then_should_return_self_for_chaining() -> None:
    chain = Arrange()
    result = chain.then("x", lambda p: p)
    assert result is chain


def test_then_should_wrap_error_in_step_error() -> None:
    def bad_fn(previous):
        raise ValueError("boom")

    with pytest.raises(StepError, match="'fail'") as exc_info:
        Arrange().then("fail", bad_fn).arrange()
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "boom"


def test_then_should_create_derived_entity_from_previous() -> None:
    def create_client(user):
        return {"type": "client", "token": f"token-for-{user['email']}"}

    scene = UserArrange().register(email="test@example.com").verified().then("api_client", create_client).arrange()
    assert scene["api_client"]["token"] == "token-for-test@example.com"
    assert scene["verified"]["verified"] is True
