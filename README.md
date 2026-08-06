# pyrrange

[![Build Status](https://github.com/othercodes/pyrrange/actions/workflows/test.yml/badge.svg)](https://github.com/othercodes/pyrrange/actions/workflows/test.yml)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=othercodes_pyrrange&metric=coverage)](https://sonarcloud.io/summary/new_code?id=othercodes_pyrrange)

Typed, composable test scenario preparation for Python.

## Why

In large codebases, the arrange phase of tests becomes the bottleneck. Fixtures are one-size-fits-all — the same `user` fixture creates a full object graph whether the test needs a simple login check or a complete checkout flow. Tests pay for setup they don't need, and there's no way to declare "give me just enough state for *this* test."

Pyrrange lets each test declare exactly the state it needs by composing small steps. Each step calls a real domain operation (not a factory), so the state is built the same way production builds it.

## Features

- Steps are plain functions — no base class, no inheritance
- Operation-based: steps call real use cases, they don't create DB rows directly
- Labeled results: reach any step's output by name, via attribute or key
- Dependency injection: mark a parameter with `on_stage()` and it comes from the scene
- Fully typed: your checker validates step arguments *and* resolves scene labels to their real types
- Inline steps via `then()` for one-off logic
- Teardown with a context manager for guaranteed cleanup
- Framework-agnostic: Django, FastAPI, or any Python project

## Requirements

- Python 3.10+
- pytest 7.0+ (optional, for `pyrrange[pytest]`)

## Installation

```bash
pip install pyrrange
```

With pytest integration:

```bash
pip install pyrrange[pytest]
```

## Usage

### Define steps

A step is a function decorated with `@step("label")`. Calling it doesn't run it — it records the call, so you can compose steps before anything executes.

```python
from pyrrange import on_stage, step

from app.accounts.models import User
from app.accounts.services import register_user, verify_email


@step("user")
def registered(email: str = "user@example.com", password: str = "secret") -> User:
    return register_user(email=email, password=password)


@step("user")
def verified(user: User = on_stage()) -> User:
    verify_email(user)
    return user
```

Steps live wherever you want — one module per domain concept works well. They're imported like any other function, so *go to definition* works and there's no inheritance to trace.

### Run them

`arrange()` runs the recorded steps in order and returns the resulting scene:

```python
from pyrrange import arrange


def test_verified_user_can_log_in():
    scene = arrange(registered(), verified())

    assert scene.user.is_verified
```

### How injection works

Mark a parameter with `on_stage()` and pyrrange fills it from the scene being built, using the parameter's own name as the label:

```python
@step("user")
def registered(email: str = "user@example.com") -> User:
    # plain default → used as-is, never injected
    # override at the call site: registered(email="other@example.com")
    ...


@step("checkout")
def purchase(
    api_client: Client = on_stage(),
    payment_method: Card = on_stage(),
    config: Config | None = None,
) -> Receipt:
    # api_client, payment_method → injected from the scene
    # config → plain default, uses None
    ...
```

Pass a label when it differs from the parameter name:

```python
@step("token")
def api_token(owner: User = on_stage("user")) -> Token:
    # reads the "user" label into a parameter called `owner`
    ...
```

The rules:

- **`on_stage()`** → injected from the scene; raises if the label isn't there yet
- **Plain default** → used as-is, never injected
- **Caller passes a keyword argument** → caller wins, even over `on_stage()`

Because `on_stage()` looks like an ordinary default, the parameter is optional at the call site *and* your remaining arguments keep being checked:

```python
arrange(registered(), verified())     # ok — you never pass `user` yourself
registered(emial="x")                 # error: did you mean "email"?
registered(email=123)                 # error: expected "str"
verified(user=1)                      # error: expected "User"
```

> **Note:** a parameter with no default at all is also injected by name. It works, but a type checker can't tell that form apart from a required argument and will ask you to pass it — use `on_stage()`.

> **Using ruff?** `on_stage()` is a sentinel, not shared mutable state, so exempt it from `B008`:
> ```toml
> [tool.ruff.lint.flake8-bugbear]
> extend-immutable-calls = ["pyrrange.on_stage"]
> ```

### Reusing a plan

Steps are recorded, so a chain is just a tuple. Declare it once and run it as many times as you like — each run is independent:

```python
PAYING_CUSTOMER = (registered(), verified(), with_card(), authenticated())


def test_checkout():
    scene = arrange(*PAYING_CUSTOMER)
```

A shortcut is a function that returns a tuple:

```python
def paying_customer(brand: str = "visa"):
    return registered(), verified(), with_card(brand=brand), authenticated()


def test_checkout_with_amex():
    scene = arrange(*paying_customer(brand="amex"))
```

No cloning, no shared state: the same records can be reused across tests and modules.

### Use in tests

Pyrrange supports four consumption patterns. All examples below use these steps:

```python
from pyrrange import Scene, arrange, on_stage, step


class AccountScene(Scene):
    user: User
    api_client: APIClient


@step("user")
def registered(email: str = "user@example.com") -> User:
    return register_user(email=email)


@step("user")
def verified(user: User = on_stage()) -> User:
    verify_email(user)
    return user


@step("api_client")
def authenticated(user: User = on_stage()) -> APIClient:
    return create_authenticated_client(user)


def delete_account(scene: AccountScene) -> None:
    scene.user.delete()
```

#### 1. Direct

Call `arrange()` and use the scene. Teardown is manual — if the test crashes, cleanup won't run.

```python
def test_checkout():
    scene = arrange(registered(), verified(), authenticated())

    response = scene.api_client.post("/checkout")

    assert response.status_code == 200
    scene.teardown()
```

#### 2. Context manager

Wrap in `with` to guarantee teardown runs, even on failure.

```python
def test_checkout():
    with arrange(registered(), verified(), authenticated(), teardown=delete_account) as scene:
        response = scene.api_client.post("/checkout")
        assert response.status_code == 200
    # teardown runs automatically on exit
```

#### 3. Scenario fixtures

Install with `pip install pyrrange[pytest]`. Use `scene_fixture` to define reusable scenarios in conftest. Each test gets a fresh scene with automatic teardown.

```python
# conftest.py
from pyrrange.pytest import scene_fixture

registered_user = scene_fixture(registered())
authenticated_user = scene_fixture(registered(), verified(), authenticated(), teardown=delete_account)

# test.py
def test_checkout(authenticated_user):
    response = authenticated_user.api_client.post("/checkout")
    assert response.status_code == 200
# teardown runs automatically via yield fixture
```

#### 4. Arrange marker

Install with `pip install pyrrange[pytest]`. Use `@pytest.mark.arrange` to declare the steps and have scene labels injected directly as test parameters — no scene unpacking.

```python
import pytest

AUTHENTICATED = (registered(), verified(), authenticated())


@pytest.mark.arrange(*AUTHENTICATED)
def test_checkout(user, api_client):
    response = api_client.post("/checkout")
    assert response.status_code == 200
# teardown runs automatically via plugin hook
```

If a scene label collides with a fixture of the same name, the scene value wins and the fixture
never runs — pyrrange emits an `ArrangeShadowWarning` so the collision doesn't pass unnoticed.
Silence it per-project with:

```toml
[tool.pytest.ini_options]
filterwarnings = ["ignore::pyrrange.pytest.ArrangeShadowWarning"]
```

The marker coexists with regular pytest fixtures:

```python
@pytest.mark.arrange(*AUTHENTICATED)
def test_checkout_logging(user, api_client, mocker):
    # user, api_client → from scene
    # mocker → from pytest as usual
    mock_log = mocker.patch("app.checkout.logger")
    api_client.post("/checkout")
    mock_log.info.assert_called_once()
```

#### Comparison

| Pattern | Teardown | Scene unpacking | Setup |
|---|---|---|---|
| Direct | Manual | `scene.label` | None |
| Context manager | Automatic | `scene.label` | None |
| Scenario fixtures | Automatic | `scene.label` | `pyrrange[pytest]` |
| Arrange marker | Automatic | Direct params | `pyrrange[pytest]` |

Each test declares only the steps it needs:

```python
arrange(registered())                                    # just a registered user
arrange(registered(), verified())                        # registered and verified
arrange(registered(), verified(), authenticated())       # plus an API client
```

### Labels

Steps are labeled by default with the function name. Use `@step("label")` to set a custom one. The same label overwrites — latest wins.

```python
@step("order")
def created(total: int = 100) -> Order:
    return create_order(total=total)


@step("order")
def paid(order: Order = on_stage()) -> Order:
    process_payment(order)
    return order


@step("receipt")
def with_receipt(order: Order = on_stage()) -> Receipt:
    return generate_receipt(order)


scene = arrange(created(), paid(), with_receipt())
order = scene.order        # the paid one — latest wins
receipt = scene.receipt
```

### Inline steps with `then()`

Use `then()` for logic that isn't worth naming with `@step`. Parameters resolve exactly the same way.

```python
from pyrrange import then


def create_api_token(user: User = on_stage()) -> Token:
    return Token.objects.create(user=user)


scene = arrange(
    registered(),
    verified(),
    then("token", create_api_token),
)
```

Works with lambdas too:

```python
scene = arrange(
    registered(),
    then("email", lambda user=on_stage(): user.email),
)
```

### Teardown

Pass `teardown` to clean up resources after a test. This is where you handle what a transaction rollback can't cover — polymorphic model deletion, external service state, file cleanup.

```python
def delete_account(scene: AccountScene) -> None:
    scene.user.delete()


with arrange(registered(), teardown=delete_account) as scene:
    ...
# teardown runs automatically on exit
```

You can also call `scene.teardown()` manually if you prefer explicit control. Without a `teardown` argument it's a no-op, so calling it is always safe.

### Typed scenes

By default `scene.user` returns `Any`. Declare a `Scene` subclass and pass it to `arrange()` for full IDE autocomplete and type checking:

```python
from pyrrange import Scene, arrange, on_stage, step


class AccountScene(Scene):
    user: User
    api_client: APIClient


scene = arrange(registered(), authenticated(), scene=AccountScene)

scene.user          # User
scene.api_client    # APIClient
```

`scene_fixture` takes it too:

```python
authenticated_user = scene_fixture(registered(), authenticated(), scene=AccountScene)
```

It's optional — without it, attribute access still works but returns `Any`. Both `scene.user` and `scene["user"]` are always available.

### When a step fails

A failing step raises `StepError` with the position in the plan, the module the step came from, and the previous result, chaining the original exception as `__cause__`:

```
StepError: Step 2/3 'verified' failed in tests.arranges.accounts
  Previous result: <User: user@example.com>
```
