from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyrrange.context import Context

if TYPE_CHECKING:
    from pyrrange._core import Arrange


class Scene:
    def __init__(self, context: Context, arrange: Arrange) -> None:
        self._context = context
        self._arrange = arrange

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
        self._arrange.teardown(self)

    def __enter__(self) -> Scene:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.teardown()

    def __repr__(self) -> str:
        return f"Scene({self._context!r})"
