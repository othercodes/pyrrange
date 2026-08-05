from __future__ import annotations

import pytest

from pyrrange._core import StepError, arrange, step


@step
def succeed():
    return "ok"


@step
def fail_with_key_error():
    return {}["missing"]


@step
def fail_with_value_error():
    raise ValueError("bad value")


@step
def fail_with_step_error():
    raise StepError(
        step_name="inner",
        step_index=1,
        total_steps=1,
        step_module="inner.module",
        previous_result=None,
    )


def test_step_error_should_include_step_name() -> None:
    with pytest.raises(StepError, match="'fail_with_key_error'"):
        arrange(succeed(), fail_with_key_error())


def test_step_error_should_include_step_index_and_total() -> None:
    with pytest.raises(StepError, match="Step 2/3"):
        arrange(succeed(), fail_with_key_error(), succeed())


def test_step_error_should_include_the_module_that_defines_the_step() -> None:
    with pytest.raises(StepError, match="tests.test_errors"):
        arrange(fail_with_key_error())


def test_step_error_should_include_previous_result() -> None:
    with pytest.raises(StepError, match="Previous result: 'ok'"):
        arrange(succeed(), fail_with_key_error())


def test_step_error_should_show_none_when_first_step_fails() -> None:
    with pytest.raises(StepError, match="Previous result: None"):
        arrange(fail_with_key_error())


def test_step_error_should_preserve_original_exception_as_cause() -> None:
    with pytest.raises(StepError) as exc_info:
        arrange(fail_with_value_error())
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "bad value"


def test_step_error_should_expose_all_attributes() -> None:
    with pytest.raises(StepError) as exc_info:
        arrange(succeed(), fail_with_key_error())
    err = exc_info.value
    assert err.step_name == "fail_with_key_error"
    assert err.step_index == 2
    assert err.total_steps == 2
    assert err.step_module == "tests.test_errors"
    assert err.previous_result == "ok"


def test_step_error_should_not_double_wrap_when_step_raises_step_error() -> None:
    with pytest.raises(StepError) as exc_info:
        arrange(fail_with_step_error())
    assert exc_info.value.step_module == "inner.module"
    assert exc_info.value.step_name == "inner"
