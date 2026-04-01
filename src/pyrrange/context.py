from __future__ import annotations

from typing import Any


class Context:
    def __init__(self) -> None:
        self._dependencies: dict[str, Any] = {}
        self._registry: dict[str, Any] = {}
        self._result: Any = None

    @property
    def result(self) -> Any:
        return self._result

    def set_result(self, label: str, value: Any) -> None:
        self._result = value
        self._registry[label] = value

    def set(self, name: str, value: Any) -> None:
        self._dependencies[name] = value

    def get(self, name: str) -> Any:
        if name not in self._dependencies:
            raise LookupError(f"Dependency '{name}' not found in context. Available: {list(self._dependencies.keys())}")
        return self._dependencies[name]

    def has(self, name: str) -> bool:
        return name in self._dependencies

    def __getitem__(self, label: str) -> Any:
        if label not in self._registry:
            raise KeyError(f"No step result for label '{label}'. Available: {list(self._registry.keys())}")
        return self._registry[label]

    def __contains__(self, label: str) -> bool:
        return label in self._registry

    def __repr__(self) -> str:
        return f"Context({list(self._registry.keys())})"
