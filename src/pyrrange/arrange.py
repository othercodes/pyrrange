"""Arrange — fluent chain of domain operations for test preparation.

Developers subclass Arrange and define @step methods. Each step is a domain
operation (register a user, verify email, purchase a plan, etc.).

Building a chain records the steps. Calling .execute() or .result replays them.
"""

from __future__ import annotations

import copy
from functools import wraps
from typing import Any, Callable, TypeVar

from pyrrange.context import Context

F = TypeVar("F", bound=Callable[..., Any])


def step(fn: F) -> F:
    """Mark a method as a recordable step.

    When called on an Arrange instance, the method is recorded (not executed).
    Execution happens later when .execute() or .result is called.

    The decorated method receives ``self`` with a bound context during execution.
    Access the previous step's result via ``self.result`` and project dependencies
    via ``self.context.get("name")``.

    Example::

        class UserArrange(Arrange):
            @step
            def register(self, email="test@example.com"):
                client.post("/api/v2/register/", {"email": email, ...})
                return User.objects.get(username=email)

            @step
            def verified(self):
                activate_account(self.result)
                return self.result
    """

    @wraps(fn)
    def wrapper(self: Arrange, *args: Any, **kwargs: Any) -> Arrange:
        self._recorded_steps.append((fn, args, kwargs))
        return self

    wrapper._original = fn  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


class Arrange:
    """Base class for defining test preparation chains.

    Subclass and define @step methods for each domain operation.
    Build chains via fluent calls, then execute with a Context.

    Example::

        class UserArrange(Arrange):
            @step
            def register(self, email="test@example.com"):
                ...

            @step
            def verified(self):
                ...

        # Inline usage
        user = UserArrange(ctx).register().verified().result

        # Sub-chain (deferred, executed by parent)
        plan_chain = PlanArrange().shared(price=9.99)
    """

    def __init__(self, context: Context | None = None) -> None:
        self._recorded_steps: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = []
        self.context: Context = context or Context()

    @property
    def result(self) -> Any:
        """Execute the chain and return the final step's result.

        This is the primary way to get the created domain object in inline usage::

            user = UserArrange(ctx).register().verified().result
        """
        return self.execute()

    def execute(self) -> Any:
        """Replay all recorded steps and return the final result.

        Each step's return value is stored in the context. Steps access it
        via ``self.result`` (which reads ``self.context.result``).

        For sub-chains, the parent step should bind a context before calling
        execute::

            @step
            def with_plan(self, plan_chain):
                plan_chain.context = self.context
                return plan_chain.execute()
        """
        for fn, args, kwargs in self._recorded_steps:
            result = fn(self, *args, **kwargs)
            self.context.set_result(result)
        return self.context.result

    def copy(self) -> Arrange:
        """Create a deep copy of this chain for safe reuse.

        Useful for scenario definitions that are shared across tests::

            default_user = UserArrange().register().verified()

            def test_a(ctx):
                user = default_user.copy().bind(ctx).result

            def test_b(ctx):
                user = default_user.copy().bind(ctx).result
        """
        return copy.deepcopy(self)

    def bind(self, context: Context) -> Arrange:
        """Bind a context to this chain (for deferred execution).

        Returns self for chaining::

            chain.bind(ctx).result
        """
        self.context = context
        return self
