from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, StepError, step
from pyrrange.context import Context


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


class ParentArrange(Arrange):
    @step
    def start(self, previous):
        return {"name": "parent"}

    @step
    def with_child(self, previous, child_chain: Arrange):
        return child_chain.bind(self.context).execute()


def _arrange(chain: Arrange) -> Context:
    """Helper to trigger .arrange() in a way that satisfies B018 lint rule."""
    return chain.arrange()


class TestStepError:
    def test_wraps_exception_with_step_name(self) -> None:
        with pytest.raises(StepError, match="'fail_with_key_error'"):
            _arrange(FailingArrange().succeed().fail_with_key_error())

    def test_includes_step_index_and_total(self) -> None:
        with pytest.raises(StepError, match="Step 2/3"):
            _arrange(FailingArrange().succeed().fail_with_key_error().succeed())

    def test_includes_arrange_class_name(self) -> None:
        with pytest.raises(StepError, match="FailingArrange"):
            _arrange(FailingArrange().fail_with_key_error())

    def test_includes_previous_result(self) -> None:
        with pytest.raises(StepError, match="Previous result: 'ok'"):
            _arrange(FailingArrange().succeed().fail_with_key_error())

    def test_previous_result_is_none_for_first_step(self) -> None:
        with pytest.raises(StepError, match="Previous result: None"):
            _arrange(FailingArrange().fail_with_key_error())

    def test_preserves_original_exception_as_cause(self) -> None:
        with pytest.raises(StepError) as exc_info:
            _arrange(FailingArrange().fail_with_value_error())
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert str(exc_info.value.__cause__) == "bad value"

    def test_step_error_attributes(self) -> None:
        with pytest.raises(StepError) as exc_info:
            _arrange(FailingArrange().succeed().fail_with_key_error())
        err = exc_info.value
        assert err.step_name == "fail_with_key_error"
        assert err.step_index == 2
        assert err.total_steps == 2
        assert err.arrange_class == "FailingArrange"
        assert err.previous_result == "ok"

    def test_sub_chain_error_propagates_through_parent(self) -> None:
        with pytest.raises(StepError, match="'fail_with_key_error'"):
            _arrange(ParentArrange().start().with_child(FailingArrange().fail_with_key_error()))

    def test_sub_chain_error_does_not_double_wrap(self) -> None:
        with pytest.raises(StepError) as exc_info:
            _arrange(ParentArrange().start().with_child(FailingArrange().fail_with_key_error()))
        # The inner StepError should propagate, not get wrapped in another StepError
        assert exc_info.value.arrange_class == "FailingArrange"
