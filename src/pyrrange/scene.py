from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyrrange.context import Context


class Scene:
    def __init__(self, context: Context, teardown: Callable[[Scene], None] | None = None) -> None:
        self._context = context
        self._teardown = teardown

    def __getitem__(self, label: str) -> Any:
        return self._context[label]

    def __getattr__(self, name: str) -> Any:
        try:
            return self._context[name]
        except KeyError:
            raise AttributeError(f"Scene has no label '{name}'. Available: {self._context!r}") from None

    def __contains__(self, label: str) -> bool:
        return label in self._context

    def teardown(self) -> None:
        if self._teardown is not None:
            self._teardown(self)

    def __enter__(self) -> Scene:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.teardown()

    def __repr__(self) -> str:
        return f"Scene({self._context!r})"
