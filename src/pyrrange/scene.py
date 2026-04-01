"""Scene — the result of executing an arrange chain.

Wraps Context (data access) and Arrange (teardown) into a single object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyrrange.context import Context

if TYPE_CHECKING:
    from pyrrange.arrange import Arrange


class Scene:
    """The result of executing an arrange chain.

    Provides dict-like access to step results and lifecycle management::

        scene = user_arrange.register().verified().arrange()
        user = scene["user"]
        scene.teardown()
    """

    def __init__(self, context: Context, arrange: Arrange) -> None:
        self._context = context
        self._arrange = arrange

    @property
    def result(self) -> Any:
        """The return value of the last executed step."""
        return self._context.result

    def __getitem__(self, label: str) -> Any:
        return self._context[label]

    def __contains__(self, label: str) -> bool:
        return label in self._context

    def teardown(self) -> None:
        """Delegates to the Arrange's teardown method."""
        self._arrange.teardown(self)

    def __repr__(self) -> str:
        return f"Scene({self._context!r})"
