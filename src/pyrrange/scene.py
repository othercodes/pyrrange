from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Scene:
    def __init__(self, results: dict[str, Any], teardown: Callable[[Scene], None] | None = None) -> None:
        self._results = results
        self._teardown = teardown

    def __getitem__(self, label: str) -> Any:
        try:
            return self._results[label]
        except KeyError:
            raise KeyError(f"No step result for label '{label}'. Available: {list(self._results)}") from None

    def __getattr__(self, name: str) -> Any:
        # Read _results out of __dict__: reaching it as an attribute on a half-built
        # instance — during copy, before __init__ runs — would re-enter __getattr__
        # forever. Going through __dict__ also leaves labels starting with "_" usable.
        results = self.__dict__.get("_results")
        if results is None:
            raise AttributeError(name)
        try:
            return results[name]
        except KeyError:
            raise AttributeError(f"Scene has no label '{name}'. Available: {list(results)}") from None

    def __contains__(self, label: str) -> bool:
        return label in self._results

    def teardown(self) -> None:
        if self._teardown is not None:
            self._teardown(self)

    def __enter__(self) -> Scene:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.teardown()

    def __repr__(self) -> str:
        return f"Scene({list(self._results)})"
