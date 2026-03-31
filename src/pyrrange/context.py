"""Context — shared state during chain execution.

The context holds:
- A registry of step results accessible by label (dict-like)
- The result of the previous step (so the next step can access it)
- Project-specific dependencies injected by the host project's fixture
"""

from __future__ import annotations

from typing import Any


class Context:
    """Shared state passed between steps during chain execution.

    The host project creates a Context in its fixture, injects project-specific
    dependencies, and passes it to the Arrange chain.

    After execution, step results are accessible by label::

        scene = UserArrange().register().verified().arrange()
        scene["register"]   # User from register step
        scene["verified"]   # User from verified step

    Example fixture::

        @pytest.fixture
        def ctx(make_plan, up_conn):
            context = Context()
            context.set("make_plan", make_plan)
            context.set("up_conn", up_conn)
            return context
    """

    def __init__(self) -> None:
        self._dependencies: dict[str, Any] = {}
        self._registry: dict[str, Any] = {}
        self._result: Any = None

    @property
    def result(self) -> Any:
        """The return value of the most recent step."""
        return self._result

    def set_result(self, label: str, value: Any) -> None:
        """Called by Arrange.execute() after each step.

        Stores the value both as the current result and in the registry under the label.
        Same label overwrites (latest wins).
        """
        self._result = value
        self._registry[label] = value

    def set(self, name: str, value: Any) -> None:
        """Register a project-specific dependency."""
        self._dependencies[name] = value

    def get(self, name: str) -> Any:
        """Retrieve a project-specific dependency.

        Raises:
            LookupError: If the dependency was not registered.
        """
        if name not in self._dependencies:
            raise LookupError(f"Dependency '{name}' not found in context. Available: {list(self._dependencies.keys())}")
        return self._dependencies[name]

    def has(self, name: str) -> bool:
        """Check if a dependency is registered."""
        return name in self._dependencies

    def __getitem__(self, label: str) -> Any:
        """Access a step result by label.

        Raises:
            KeyError: If no step with that label has been executed.
        """
        if label not in self._registry:
            raise KeyError(f"No step result for label '{label}'. Available: {list(self._registry.keys())}")
        return self._registry[label]

    def __contains__(self, label: str) -> bool:
        """Check if a step result exists for a label."""
        return label in self._registry

    def __repr__(self) -> str:
        labels = list(self._registry.keys())
        return f"Context({labels})"
