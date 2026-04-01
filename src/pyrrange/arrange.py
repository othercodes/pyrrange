"""Arrange — fluent chain of domain operations for test preparation.

Every step — whether @step or .then() — receives the previous result as its
first argument and returns the next result. Explicit data flow, no hidden state.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, overload

from pyrrange.context import Context
from pyrrange.scene import Scene

F = TypeVar("F", bound=Callable[..., Any])


class StepError(Exception):
    """Wraps a step failure with diagnostic info: step name, index, previous result."""

    def __init__(
        self,
        step_name: str,
        step_index: int,
        total_steps: int,
        arrange_class: str,
        previous_result: Any,
        cause: BaseException,
    ) -> None:
        self.step_name = step_name
        self.step_index = step_index
        self.total_steps = total_steps
        self.arrange_class = arrange_class
        self.previous_result = previous_result
        super().__init__(
            f"Step {step_index}/{total_steps} '{step_name}' failed on {arrange_class}\n"
            f"  Previous result: {previous_result!r}"
        )


@overload
def step(fn: F) -> F: ...  # pragma: no cover


@overload
def step(label: str) -> Callable[[F], F]: ...  # pragma: no cover


def step(fn: F | str | None = None, label: str | None = None) -> F | Callable[[F], F]:  # type: ignore[misc]
    """Mark a method as a recordable step.

    Usage::

        @step
        def register(self, previous, email="test@example.com"):
            ...

        @step("user")
        def register(self, previous, email="test@example.com"):
            ...
    """
    if isinstance(fn, str):
        return _make_step_decorator(fn)

    if fn is None:
        return _make_step_decorator(label)

    return _make_step_decorator(None)(fn)


def _make_step_decorator(label: str | None) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        step_label = label or fn.__name__

        @wraps(fn)
        def wrapper(self: Arrange, *args: Any, **kwargs: Any) -> Arrange:
            self._recorded_steps.append(_StepRecord(fn, step_label, args, kwargs))
            return self

        wrapper._original = fn  # type: ignore[attr-defined]
        wrapper._step_label = step_label  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


class _StepRecord:
    __slots__ = ("args", "fn", "kwargs", "label")

    def __init__(self, fn: Callable[..., Any], label: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs

    def execute(self, arrange: Arrange, previous: Any) -> Any:
        return self.fn(arrange, previous, *self.args, **self.kwargs)


class _ThenRecord:
    __slots__ = ("args", "fn", "kwargs", "label")

    def __init__(self, fn: Callable[..., Any], label: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs

    def execute(self, arrange: Arrange, previous: Any) -> Any:
        return self.fn(previous, *self.args, **self.kwargs)


class Arrange:
    """Base class for test preparation chains.

    Subclass and define @step methods for each domain operation::

        class UserArrange(Arrange):
            @step("user")
            def register(self, previous, email="test@example.com"):
                ...

        scene = UserArrange().register().verified().arrange()
        user = scene["user"]
    """

    def __init__(self, context: Context | None = None) -> None:
        self._recorded_steps: list[_StepRecord | _ThenRecord] = []
        self.context: Context = context or Context()

    def then(self, label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Arrange:
        """Add an inline step: ``fn(previous, *args, **kwargs)`` stored under ``label``."""
        self._recorded_steps.append(_ThenRecord(fn, label, args, kwargs))
        return self

    def teardown(self, scene: Scene) -> None:
        """Override to clean up resources created during arrange."""

    def arrange(self) -> Scene:
        """Execute the chain and return a Scene with labeled results."""
        return self.execute()

    def execute(self) -> Scene:
        """Replay all recorded steps and return a Scene."""
        total = len(self._recorded_steps)
        for index, record in enumerate(self._recorded_steps, start=1):
            try:
                result = record.execute(self, self.context.result)
            except StepError:
                raise
            except Exception as exc:
                raise StepError(
                    step_name=record.label,
                    step_index=index,
                    total_steps=total,
                    arrange_class=type(self).__name__,
                    previous_result=self.context.result,
                    cause=exc,
                ) from exc
            self.context.set_result(record.label, result)
        return Scene(self.context, self)

    def copy(self) -> Arrange:
        """Create a deep copy of this chain for safe reuse."""
        return copy.deepcopy(self)

    def bind(self, context: Context) -> Arrange:
        """Bind a context to this chain for deferred execution."""
        self.context = context
        return self
