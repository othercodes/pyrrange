from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, Protocol, TypeVar, overload

from pyrrange.context import Context
from pyrrange.scene import Scene

F = TypeVar("F", bound=Callable[..., Any])
A = TypeVar("A", bound="Arrange")


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


class _StepMethod(Protocol):
    """A recorded step: takes the step's own arguments, returns the receiver so chains keep its type.

    A decorator cannot express "this signature, minus the injected params, returning Self".
    ``ParamSpec`` would demand the injected params at the call site — ``.verified()`` would
    require ``user`` — which defeats injection. A generic ``__get__`` binds to the receiver
    instead, at the cost of unchecked call arguments.
    """

    def __get__(self, obj: A, objtype: type[A] | None = None) -> Callable[..., A]: ...  # pragma: no cover


@overload
def step(fn: F) -> _StepMethod: ...  # pragma: no cover


@overload
def step(fn: str) -> Callable[[F], _StepMethod]: ...  # pragma: no cover


def step(fn: Any = None, label: str | None = None) -> Any:
    if isinstance(fn, str):
        return _make_step_decorator(fn)

    if fn is None:
        return _make_step_decorator(label)

    return _make_step_decorator(None)(fn)


def _cache_params(fn: Callable[..., Any], skip_self: bool) -> tuple[inspect.Parameter, ...]:
    params = tuple(inspect.signature(fn).parameters.values())
    if skip_self and params:
        params = params[1:]
    return params


def _make_step_decorator(label: str | None) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        step_label = label or fn.__name__
        cached_params = _cache_params(fn, skip_self=True)

        @wraps(fn)
        def wrapper(self: Arrange, *args: Any, **kwargs: Any) -> Arrange:
            self._recorded_steps.append(_StepRecord(fn, step_label, args, kwargs, cached_params))
            return self

        wrapper.__annotations__ = {"return": Arrange}
        wrapper._original = fn  # type: ignore[attr-defined]
        wrapper._step_label = step_label  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def _resolve_kwargs(
    params: tuple[inspect.Parameter, ...],
    context: Context,
    recorded_args: tuple[Any, ...],
    recorded_kwargs: dict[str, Any],
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}

    for param in params:
        if param.name in recorded_kwargs:
            continue
        if param.default is inspect.Parameter.empty and param.name in context:
            resolved[param.name] = context[param.name]

    unresolved = [p for p in params if p.name not in resolved and p.name not in recorded_kwargs]
    for i, arg in enumerate(recorded_args):
        if i < len(unresolved):
            resolved[unresolved[i].name] = arg

    resolved.update(recorded_kwargs)

    return resolved


class _StepRecord:
    __slots__ = ("args", "fn", "kwargs", "label", "params")

    def __init__(
        self,
        fn: Callable[..., Any],
        label: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        params: tuple[inspect.Parameter, ...],
    ) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs
        self.params = params

    def execute(self, arrange: Arrange) -> Any:
        kwargs = _resolve_kwargs(self.params, arrange._context, self.args, self.kwargs)
        return self.fn(arrange, **kwargs)


class _ThenRecord:
    __slots__ = ("args", "fn", "kwargs", "label", "params")

    def __init__(
        self,
        fn: Callable[..., Any],
        label: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        params: tuple[inspect.Parameter, ...],
    ) -> None:
        self.fn = fn
        self.label = label
        self.args = args
        self.kwargs = kwargs
        self.params = params

    def execute(self, _arrange: Arrange) -> Any:
        kwargs = _resolve_kwargs(self.params, _arrange._context, self.args, self.kwargs)
        return self.fn(**kwargs)


class Arrange:
    def __init__(self) -> None:
        self._recorded_steps: list[_StepRecord | _ThenRecord] = []
        self._context: Context = Context()

    def clone(self: A) -> A:
        new: A = type(self)()
        new._recorded_steps = self._recorded_steps.copy()
        return new

    def then(self: A, label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> A:
        self._recorded_steps.append(_ThenRecord(fn, label, args, kwargs, _cache_params(fn, skip_self=False)))
        return self

    def teardown(self, scene: Scene) -> None:
        """Hook for cleaning up resources after a test.

        Override in subclasses to release external state that cannot be
        rolled back automatically — polymorphic model deletion, external
        service cleanup, file removal, etc. The base implementation is a
        no-op so calling ``scene.teardown()`` is always safe.

        Called automatically when a Scene is used as a context manager
        (``with ... as scene:``), or manually via ``scene.teardown()``.

        :param scene: The Scene produced by ``arrange()``. Use
            ``scene["label"]`` or ``scene.label`` to access step results
            that need cleanup.
        """

    def arrange(self) -> Scene:
        total = len(self._recorded_steps)
        for index, record in enumerate(self._recorded_steps, start=1):
            try:
                result = record.execute(self)
            except StepError:
                raise
            except Exception as exc:
                raise StepError(
                    step_name=record.label,
                    step_index=index,
                    total_steps=total,
                    arrange_class=type(self).__name__,
                    previous_result=self._context._last_result,
                ) from exc
            self._context.set_result(record.label, result)
        scene_cls = getattr(type(self), "SceneType", Scene)
        return scene_cls(self._context, self)
