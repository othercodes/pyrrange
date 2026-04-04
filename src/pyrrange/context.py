from __future__ import annotations

from typing import Any


class Context:
    def __init__(self) -> None:
        self._registry: dict[str, Any] = {}
        self._result: Any = None

    @property
    def result(self) -> Any:
        return self._result

    def set_result(self, label: str, value: Any) -> None:
        self._result = value
        self._registry[label] = value

    def __getitem__(self, label: str) -> Any:
        if label not in self._registry:
            raise KeyError(f"No step result for label '{label}'. Available: {list(self._registry.keys())}")
        return self._registry[label]

    def __contains__(self, label: str) -> bool:
        return label in self._registry

    def __repr__(self) -> str:
        return f"Context({list(self._registry.keys())})"
