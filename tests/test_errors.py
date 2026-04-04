from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, StepError, step
from pyrrange.scene import Scene


class FailingArrange(Arrange):
    @step
    def succeed(self, previous):
        return "ok"

    @step
    def fail_with_key_error(self, previous):
        return {}["missing"]

    @step
    def fail_with_value_error(self, previous):
        raise ValueError("bad value")

    @step
    def fail_with_step_error(self, previous):
        raise StepError(
            step_name="inner",
            step_index=1,
            total_steps=1,
            arrange_class="Inner",
            previous_result=None,
        )


def _arrange(chain: Arrange) -> Scene:
    return chain.arrange()


def test_step_error_should_include_step_name() -> None:
    with pytest.raises(StepError, match="'fail_with_key_error'"):
        _arrange(FailingArrange().succeed().fail_with_key_error())


def test_step_error_should_include_step_index_and_total() -> None:
    with pytest.raises(StepError, match="Step 2/3"):
        _arrange(FailingArrange().succeed().fail_with_key_error().succeed())


def test_step_error_should_include_arrange_class_name() -> None:
    with pytest.raises(StepError, match="FailingArrange"):
        _arrange(FailingArrange().fail_with_key_error())


def test_step_error_should_include_previous_result() -> None:
    with pytest.raises(StepError, match="Previous result: 'ok'"):
        _arrange(FailingArrange().succeed().fail_with_key_error())


def test_step_error_should_show_none_when_first_step_fails() -> None:
    with pytest.raises(StepError, match="Previous result: None"):
        _arrange(FailingArrange().fail_with_key_error())


def test_step_error_should_preserve_original_exception_as_cause() -> None:
    with pytest.raises(StepError) as exc_info:
        _arrange(FailingArrange().fail_with_value_error())
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "bad value"


def test_step_error_should_expose_all_attributes() -> None:
    with pytest.raises(StepError) as exc_info:
        _arrange(FailingArrange().succeed().fail_with_key_error())
    err = exc_info.value
    assert err.step_name == "fail_with_key_error"
    assert err.step_index == 2
    assert err.total_steps == 2
    assert err.arrange_class == "FailingArrange"
    assert err.previous_result == "ok"


def test_step_error_should_not_double_wrap_when_step_raises_step_error() -> None:
    with pytest.raises(StepError) as exc_info:
        _arrange(FailingArrange().fail_with_step_error())
    assert exc_info.value.arrange_class == "Inner"
    assert exc_info.value.step_name == "inner"
