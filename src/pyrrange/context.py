"""Context — shared state during chain execution.

The context holds:
- The result of the previous step (so the next step can access it)
- Project-specific dependencies injected by the host project's fixture
"""

from __future__ import annotations

from typing import Any


class Context:
    """Shared state passed between steps during chain execution.

    The host project creates a Context in its ``prepare`` or ``ctx`` fixture,
    injects project-specific dependencies, and passes it to the Arrange chain.

    Example::

        @pytest.fixture
        def ctx(make_plan, up_conn):
            context = Context()
            context.set("make_plan", make_plan)
            context.set("up_conn", up_conn)
            return context
    """

    def __init__(self) -> None:
        self._dependencies: dict[str, Any] = {}
        self._result: Any = None
        self._results: list[Any] = []

    @property
    def result(self) -> Any:
        """The return value of the most recent step."""
        return self._result

    @property
    def results(self) -> list[Any]:
        """All step results in execution order."""
        return list(self._results)

    def set_result(self, value: Any) -> None:
        """Called by Arrange.execute() after each step."""
        self._result = value
        self._results.append(value)

    def set(self, name: str, value: Any) -> None:
        """Register a project-specific dependency."""
        self._dependencies[name] = value

    def get(self, name: str) -> Any:
        """Retrieve a project-specific dependency.

        Raises:
            LookupError: If the dependency was not registered.
        """
        if name not in self._dependencies:
            raise LookupError(
                f"Dependency '{name}' not found in context. "
                f"Available: {list(self._dependencies.keys())}"
            )
        return self._dependencies[name]

    def has(self, name: str) -> bool:
        """Check if a dependency is registered."""
        return name in self._dependencies
