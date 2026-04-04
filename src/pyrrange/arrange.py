from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, overload

from pyrrange.context import Context
from pyrrange.scene import Scene

F = TypeVar("F", bound=Callable[..., Any])


class StepError(Exception):
    def __init__(
        self,
        step_name: str,
        step_index: int,
        total_steps: int,
        arrange_class: str,
        previous_result: Any,
    ) -> None:
        self.step_name = step_name
        self.step_index = step_index
        self.total_steps = total_steps
        self.arrange_class = arrange_class
        self.previous_result = previous_result
        super().__init__(
            f"Step {step_index}/{total_steps} '{step_name}' failed on {arrange_class}\n"
            f"  Previous result: {previous_result!r}"
        )


@overload
def step(fn: F) -> F: ...  # pragma: no cover


@overload
def step(label: str) -> Callable[[F], F]: ...  # pragma: no cover


def step(fn: F | str | None = None, label: str | None = None) -> F | Callable[[F], F]:  # type: ignore[misc]
    if isinstance(fn, str):
        return _make_step_decorator(fn)

    if fn is None:
        return _make_step_decorator(label)

    return _make_step_decorator(None)(fn)


def _make_step_decorator(label: str | None) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        step_label = label or fn.__name__

        @wraps(fn)
        def wrapper(self: Arrange, *args: Any, **kwargs: Any) -> Arrange:
            self._recorded_steps.append(_StepRecord(fn, step_label, args, kwargs))
            return self

        wrapper._original = fn  # type: ignore[attr-defined]
        wrapper._step_label = step_label  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


class _StepRecord:
    __slots__ = ("args", "fn", "kwargs", "label")

    def __init__(self, fn: Callable[..., Any], label: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs

    def execute(self, arrange: Arrange, previous: Any) -> Any:
        return self.fn(arrange, previous, *self.args, **self.kwargs)


class _ThenRecord:
    __slots__ = ("args", "fn", "kwargs", "label")

    def __init__(self, fn: Callable[..., Any], label: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs

    def execute(self, _arrange: Arrange, previous: Any) -> Any:
        return self.fn(previous, *self.args, **self.kwargs)


class Arrange:
    def __init__(self) -> None:
        self._recorded_steps: list[_StepRecord | _ThenRecord] = []
        self.context: Context = Context()

    def then(self, label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Arrange:
        self._recorded_steps.append(_ThenRecord(fn, label, args, kwargs))
        return self

    def teardown(self, scene: Scene) -> None:
        pass

    def arrange(self) -> Scene:
        total = len(self._recorded_steps)
        for index, record in enumerate(self._recorded_steps, start=1):
            try:
                result = record.execute(self, self.context.result)
            except StepError:
                raise
            except Exception as exc:
                raise StepError(
                    step_name=record.label,
                    step_index=index,
                    total_steps=total,
                    arrange_class=type(self).__name__,
                    previous_result=self.context.result,
                ) from exc
            self.context.set_result(record.label, result)
        return Scene(self.context, self)
