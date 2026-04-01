"""Arrange — fluent chain of domain operations for test preparation.

Developers subclass Arrange and define @step methods. Each step is a domain
operation (register a user, verify email, purchase a plan, etc.).

Building a chain records the steps. Calling .arrange() replays them and
returns a registry of labeled results.

Every step — whether @step or .then() — receives the previous result as its
first argument and returns the next result. Explicit data flow, no hidden state.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, overload

from pyrrange.context import Context

F = TypeVar("F", bound=Callable[..., Any])


class StepError(Exception):
    """Raised when a step fails during chain execution.

    Wraps the original exception with diagnostic information:
    which step failed, its position in the chain, and the previous result.
    """

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

    Can be used with or without a label::

        @step
        def register(self, previous, email="test@example.com"):
            ...  # label defaults to "register"

        @step("user")
        def register(self, previous, email="test@example.com"):
            ...  # label is "user"

    The decorated method receives the previous step's result as its first
    argument (after self). Return value becomes the next result.
    """
    if isinstance(fn, str):
        # Called as @step("label")
        return _make_step_decorator(fn)

    if fn is None:
        # Called as @step(label="label")
        return _make_step_decorator(label)

    # Called as @step (no parentheses)
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
    """Internal record of a @step method to be executed."""

    __slots__ = ("args", "fn", "kwargs", "label")

    def __init__(self, fn: Callable[..., Any], label: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs

    def execute(self, arrange: Arrange, previous: Any) -> Any:
        return self.fn(arrange, previous, *self.args, **self.kwargs)


class _ThenRecord:
    """Internal record of a .then() step to be executed."""

    __slots__ = ("args", "fn", "kwargs", "label")

    def __init__(self, fn: Callable[..., Any], label: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs

    def execute(self, arrange: Arrange, previous: Any) -> Any:
        return self.fn(previous, *self.args, **self.kwargs)


class Arrange:
    """Base class for defining test preparation chains.

    Subclass and define @step methods for each domain operation.
    Build chains via fluent calls, then call .arrange() to execute.

    Every step receives the previous result as its first argument::

        class UserArrange(Arrange):
            @step("user")
            def register(self, previous, email="test@example.com"):
                # previous is None (first step)
                ...
                return user

            @step("user")
            def verified(self, user):
                # user = return value of register
                activate_account(user)
                return user

        # Inline steps with .then()
        scene = (
            UserArrange()
                .register()
                .verified()
                .then("api_client", create_authenticated_client)
                .arrange()
        )
    """

    def __init__(self, context: Context | None = None) -> None:
        self._recorded_steps: list[_StepRecord | _ThenRecord] = []
        self.context: Context = context or Context()

    def then(self, label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Arrange:
        """Add an inline step that receives the previous result.

        The function is called with ``fn(previous_result, *args, **kwargs)``
        and its return value is stored under ``label``::

            .then("api_client", create_authenticated_client)
            .then("plan", lambda user: make_plan(user, {"proxy_type": "shared"}))
        """
        self._recorded_steps.append(_ThenRecord(fn, label, args, kwargs))
        return self

    def teardown(self, scene: Context) -> None:
        """Override to clean up resources created during arrange.

        Called by ``scene.teardown()`` after the test completes::

            class UserArrange(Arrange):
                def teardown(self, scene):
                    user = scene["user"]
                    user.delete()

            scene = user_arrange.register().arrange()
            # ... test ...
            scene.teardown()
        """

    def arrange(self) -> Context:
        """Execute the chain and return the context with labeled results.

        This is the primary entry point to trigger execution::

            scene = UserArrange().register().verified().arrange()
            user = scene["register"]
        """
        return self.execute()

    def execute(self) -> Context:
        """Replay all recorded steps and return the context.

        Each step receives the previous result as its first argument.
        The return value is stored in the context under the step's label.
        """
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
        self.context.set_teardown(self.teardown)
        return self.context

    def copy(self) -> Arrange:
        """Create a deep copy of this chain for safe reuse."""
        return copy.deepcopy(self)

    def bind(self, context: Context) -> Arrange:
        """Bind a context to this chain (for deferred execution).

        Returns self for chaining::

            scene = chain.bind(ctx).arrange()
        """
        self.context = context
        return self
