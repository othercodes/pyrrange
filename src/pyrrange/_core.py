from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, overload

from pyrrange.context import Context
from pyrrange.scene import Scene

P = ParamSpec("P")
S = TypeVar("S", bound=Scene)


class _OnStage:
    __slots__ = ("label",)

    def __init__(self, label: str | None) -> None:
        self.label = label

    def __repr__(self) -> str:
        return f"on_stage({self.label!r})" if self.label else "on_stage()"


def on_stage(label: str | None = None) -> Any:
    """Mark a step parameter as already in the scene, to be injected when the step runs.

    A type checker sees an ordinary default, so the parameter is optional at the call
    site and the remaining arguments keep being checked. At runtime the default is this
    sentinel, so the value is taken from the scene being built instead.

    :param label: Scene label to read. Defaults to the parameter's own name, which is
        what you want unless the label and the parameter need different names.
    """
    return _OnStage(label)


class StepError(Exception):
    def __init__(
        self,
        step_name: str,
        step_index: int,
        total_steps: int,
        step_module: str,
        previous_result: Any,
    ) -> None:
        self.step_name = step_name
        self.step_index = step_index
        self.total_steps = total_steps
        self.step_module = step_module
        self.previous_result = previous_result
        super().__init__(
            f"Step {step_index}/{total_steps} '{step_name}' failed in {step_module}\n"
            f"  Previous result: {previous_result!r}"
        )


class Record:
    """A step call captured for later execution. Produced by calling a decorated step."""

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

    def execute(self, context: Context) -> Any:
        return self.fn(**_resolve_kwargs(self.params, context, self.args, self.kwargs))

    def __repr__(self) -> str:
        return f"Record({self.label!r}, {self.fn.__name__})"


class _Step(Protocol[P]):
    """A decorated step: same call signature as the function, but records instead of running."""

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Record: ...  # pragma: no cover


@overload
def step(fn: Callable[P, object]) -> _Step[P]: ...  # pragma: no cover


@overload
def step(fn: str) -> Callable[[Callable[P, object]], _Step[P]]: ...  # pragma: no cover


def step(fn: Any = None, label: str | None = None) -> Any:
    """Turn a function into a step: calling it records the call instead of running it."""
    if isinstance(fn, str):
        return _make_step_decorator(fn)

    if fn is None:
        return _make_step_decorator(label)

    return _make_step_decorator(None)(fn)


def _cache_params(fn: Callable[..., Any]) -> tuple[inspect.Parameter, ...]:
    return tuple(inspect.signature(fn).parameters.values())


def _make_step_decorator(label: str | None) -> Callable[[Callable[..., Any]], Any]:
    def decorator(fn: Callable[..., Any]) -> Any:
        if getattr(fn, "_is_step", False):
            raise TypeError(
                f"'{fn.__name__}' is already a step; stacking @step would record the inner "
                f"decorator instead of the function, leaving a Record in the scene"
            )

        step_label = label or fn.__name__
        params = _cache_params(fn)

        @wraps(fn)
        def record(*args: Any, **kwargs: Any) -> Record:
            return Record(fn, step_label, args, kwargs, params)

        record._is_step = True  # type: ignore[attr-defined]
        return record

    return decorator


def then(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Record:
    """Record a one-off callable as a step, for logic not worth naming with @step."""
    return Record(fn, label, args, kwargs, _cache_params(fn))


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
        if isinstance(param.default, _OnStage):
            # Declaring on_stage() asserts the label is there; a missing one is a
            # programming error, so let Context raise and list what is available.
            resolved[param.name] = context[param.default.label or param.name]
            continue
        if param.default is inspect.Parameter.empty and param.name in context:
            resolved[param.name] = context[param.name]

    unresolved = [p for p in params if p.name not in resolved and p.name not in recorded_kwargs]
    for i, arg in enumerate(recorded_args):
        if i < len(unresolved):
            resolved[unresolved[i].name] = arg

    resolved.update(recorded_kwargs)

    return resolved


@overload
def arrange(
    *records: Record,
    scene: type[S],
    teardown: Callable[[S], None] | None = None,
) -> S: ...  # pragma: no cover


@overload
def arrange(
    *records: Record,
    teardown: Callable[[Scene], None] | None = None,
) -> Scene: ...  # pragma: no cover


def arrange(
    *records: Record,
    scene: type[Scene] = Scene,
    teardown: Callable[[Any], None] | None = None,
) -> Any:
    """Run the recorded steps in order and return the resulting scene.

    :param scene: Scene subclass to build, declaring the labels for a type checker.
    :param teardown: Called with the scene on ``teardown()`` or on leaving a ``with``.
    """
    if not (isinstance(scene, type) and issubclass(scene, Scene)):
        got = scene.__name__ if isinstance(scene, type) else type(scene).__name__
        raise TypeError(f"scene must be a Scene subclass, got {got}")

    for record in records:
        if not isinstance(record, Record):
            raise TypeError(
                f"arrange() expects steps, got {type(record).__name__}. "
                f"Call the step to record it: arrange(registered()), not arrange(registered)"
            )

    context = Context()
    total = len(records)

    for index, record in enumerate(records, start=1):
        try:
            result = record.execute(context)
        except StepError:
            raise
        except Exception as exc:
            raise StepError(
                step_name=record.label,
                step_index=index,
                total_steps=total,
                step_module=getattr(record.fn, "__module__", "<unknown>"),
                previous_result=context._last_result,
            ) from exc
        context.set_result(record.label, result)

    return scene(context, teardown)
