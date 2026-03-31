"""Arrange — fluent chain of domain operations for test preparation.

Developers subclass Arrange and define @step methods. Each step is a domain
operation (register a user, verify email, purchase a plan, etc.).

Building a chain records the steps. Calling .arrange() replays them and
returns a registry of labeled results.
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
        def register(self, email="test@example.com"):
            ...  # label defaults to "register"

        @step("user")
        def register(self, email="test@example.com"):
            ...  # label is "user"

    When called on an Arrange instance, the method is recorded (not executed).
    Execution happens when .arrange() is called.
    """
    if isinstance(fn, str):
        # Called as @step("label")
        explicit_label = fn
        return _make_step_decorator(explicit_label)

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
            self._recorded_steps.append((fn, step_label, args, kwargs))
            return self

        wrapper._original = fn  # type: ignore[attr-defined]
        wrapper._step_label = step_label  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


class Arrange:
    """Base class for defining test preparation chains.

    Subclass and define @step methods for each domain operation.
    Build chains via fluent calls, then call .arrange() to execute.

    Example::

        class UserArrange(Arrange):
            @step
            def register(self, email="test@example.com"):
                ...

            @step("user")
            def verified(self):
                ...

        # Execute and access results by label
        scene = UserArrange().register().verified().arrange()
        user = scene["user"]

        # Sub-chain (deferred, executed by parent)
        plan_chain = PlanArrange().shared(price=9.99)
    """

    def __init__(self, context: Context | None = None) -> None:
        self._recorded_steps: list[tuple[Callable[..., Any], str, tuple[Any, ...], dict[str, Any]]] = []
        self.context: Context = context or Context()

    def arrange(self) -> Context:
        """Execute the chain and return the context with labeled results.

        This is the primary entry point to trigger execution::

            scene = UserArrange().register().verified().arrange()
            user = scene["register"]
            # or scene["verified"]
        """
        return self.execute()

    def execute(self) -> Context:
        """Replay all recorded steps and return the context.

        Each step's return value is stored in the context under its label.
        Steps access the previous result via ``self.context.result``
        and dependencies via ``self.context.get("name")``.

        For sub-chains, the parent step should bind context before calling
        execute::

            @step("plan")
            def with_plan(self, plan_chain):
                return plan_chain.bind(self.context).execute()
        """
        total = len(self._recorded_steps)
        for index, (fn, label, args, kwargs) in enumerate(self._recorded_steps, start=1):
            try:
                result = fn(self, *args, **kwargs)
            except StepError:
                raise
            except Exception as exc:
                raise StepError(
                    step_name=label,
                    step_index=index,
                    total_steps=total,
                    arrange_class=type(self).__name__,
                    previous_result=self.context.result,
                    cause=exc,
                ) from exc
            self.context.set_result(label, result)
        return self.context

    def copy(self) -> Arrange:
        """Create a deep copy of this chain for safe reuse.

        Useful for scenario definitions that are shared across tests::

            default_user = UserArrange().register().verified()

            def test_a(ctx):
                scene = default_user.copy().bind(ctx).arrange()

            def test_b(ctx):
                scene = default_user.copy().bind(ctx).arrange()
        """
        return copy.deepcopy(self)

    def bind(self, context: Context) -> Arrange:
        """Bind a context to this chain (for deferred execution).

        Returns self for chaining::

            scene = chain.bind(ctx).arrange()
        """
        self.context = context
        return self
