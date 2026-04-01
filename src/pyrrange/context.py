"""Context — data container for step results and project dependencies."""

from __future__ import annotations

from typing import Any


class Context:
    """Holds step results (by label) and project-specific dependencies.

    Step results are accessible via dict-like syntax::

        scene = UserArrange().register().verified().arrange()
        user = scene["user"]
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
        """Store a step result. Same label overwrites (latest wins)."""
        self._result = value
        self._registry[label] = value

    def set(self, name: str, value: Any) -> None:
        """Register a project-specific dependency."""
        self._dependencies[name] = value

    def get(self, name: str) -> Any:
        """Retrieve a dependency. Raises LookupError if not found."""
        if name not in self._dependencies:
            raise LookupError(f"Dependency '{name}' not found in context. Available: {list(self._dependencies.keys())}")
        return self._dependencies[name]

    def has(self, name: str) -> bool:
        """Check if a dependency is registered."""
        return name in self._dependencies

    def __getitem__(self, label: str) -> Any:
        if label not in self._registry:
            raise KeyError(f"No step result for label '{label}'. Available: {list(self._registry.keys())}")
        return self._registry[label]

    def __contains__(self, label: str) -> bool:
        return label in self._registry

    def __repr__(self) -> str:
        return f"Context({list(self._registry.keys())})"
