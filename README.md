# pyrrange

[![Build Status](https://github.com/othercodes/pyrrange/actions/workflows/test.yml/badge.svg)](https://github.com/othercodes/pyrrange/actions/workflows/test.yml)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=othercodes_pyrrange&metric=coverage)](https://sonarcloud.io/summary/new_code?id=othercodes_pyrrange)

Expressive, fluent test scenario preparation for Python.

## Why

In large codebases, the arrange phase of tests becomes the bottleneck. Fixtures are one-size-fits-all — the same `user` fixture creates a full object graph whether the test needs a simple login check or a complete checkout flow. Tests pay for setup they don't need, and there's no way to declare "give me just enough state for *this* test."

Pyrrange solves this by letting tests declare exactly what state they need through a fluent chain of operations. Each step calls a real domain operation (not a factory), so the state is built the same way production builds it.

## Features

- Fluent, chainable API for test state preparation
- Operation-based: steps call real use cases, not create DB rows directly
- Labeled results: access any step's output by name via attribute or dict access
- Automatic dependency injection: step parameters are resolved from context by name
- Optional typed scenes: declare a `SceneType` for full IDE autocomplete and type checking
- Inline steps via `.then()` for ad-hoc logic
- Teardown support with context manager for guaranteed cleanup
- Framework-agnostic: works with Django, FastAPI, or any Python project

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

### Define an Arrange

Subclass `Arrange` and define `@step` methods. Each step declares what it needs via its parameter names — pyrrange injects values from the context automatically.

```python
from pyrrange import Arrange, step


class AccountArrange(Arrange):
    @step("user")
    def register(self, email="user@example.com", password="secret"):
        user = register_user(email=email, password=password)
        return user

    @step("user")
    def verified(self, user):
        verify_email(user)
        return user

    @step("user")
    def as_admin(self, user):
        user.is_admin = True
        user.save()
        return user
```

### How injection works

Parameters are resolved using a simple rule:

- **No default value** + name matches a label in context → **injected automatically**
- **Has default value** → **uses the default**, never injected (safe from silent overrides)
- **Caller provides a value** → **caller always wins**

```python
@step("user")
def register(self, email="user@example.com"):
    # `email` has a default → not injected, uses "user@example.com"
    # Override via chain: .register(email="other@example.com")
    ...

@step("user")
def verified(self, user):
    # `user` has no default → injected from context["user"]
    ...

@step("checkout")
def purchase(self, api_client, payment_method, config=None):
    # `api_client` → injected from context["api_client"]
    # `payment_method` → injected from context["payment_method"]
    # `config` has a default → not injected, uses None
    ...
```

This means every dependency is **typed in the signature** — your IDE gives autocomplete and your type checker validates usage.

### Use in tests

Pyrrange supports four consumption patterns. All examples below use the same arrange:

```python
from pyrrange import Arrange, Scene, step

class AccountArrange(Arrange):
    class SceneType(Scene):
        user: User
        api_client: APIClient

    @step("user")
    def register(self, email="user@example.com"):
        return register_user(email=email)

    @step("user")
    def verified(self, user):
        verify_email(user)
        return user

    @step("api_client")
    def with_client(self, user):
        return create_authenticated_client(user)

    def teardown(self, scene):
        scene.user.delete()
```

#### 1. Direct

Call `.arrange()` and use the scene. Teardown is manual — if the test crashes, cleanup won't run.

```python
def test_checkout():
    scene = AccountArrange().register().verified().with_client().arrange()
    response = scene.api_client.post("/checkout")
    assert response.status_code == 200
    scene.teardown()
```

#### 2. Context manager

Wrap in `with` to guarantee teardown runs, even on failure.

```python
def test_checkout():
    with AccountArrange().register().verified().with_client().arrange() as scene:
        response = scene.api_client.post("/checkout")
        assert response.status_code == 200
    # teardown runs automatically on exit
```

#### 3. Scenario fixtures

Install with `pip install pyrrange[pytest]`. Use `scene_fixture` to define reusable scenarios in conftest. Each test gets a fresh clone with automatic teardown.

```python
# conftest.py
from pyrrange.pytest import scene_fixture

registered = scene_fixture(AccountArrange().register())
authenticated = scene_fixture(AccountArrange().register().verified().with_client())

# test.py
def test_checkout(authenticated):
    response = authenticated.api_client.post("/checkout")
    assert response.status_code == 200
# teardown runs automatically via yield fixture
```

#### 4. Arrange marker

Install with `pip install pyrrange[pytest]`. Use `@pytest.mark.arrange` to declare a chain and have scene labels injected directly as test parameters — no scene unpacking.

```python
import pytest

_authenticated = AccountArrange().register().verified().with_client()

@pytest.mark.arrange(_authenticated)
def test_checkout(user, api_client):
    response = api_client.post("/checkout")
    assert response.status_code == 200
# teardown runs automatically via plugin hook
```

The marker coexists with regular pytest fixtures:

```python
@pytest.mark.arrange(_authenticated)
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
# Just a registered user
AccountArrange().register()

# Registered and verified
AccountArrange().register().verified()

# Full authenticated user with API client
AccountArrange().register().verified().with_client()
```

### Labels

Steps are labeled by default with the method name. Use `@step("label")` to set a custom label. Same label overwrites (latest wins).

```python
class OrderArrange(Arrange):
    @step("order")
    def create(self, total=100):
        return create_order(total=total)

    @step("order")
    def paid(self, order):
        process_payment(order)
        return order

    @step("receipt")
    def with_receipt(self, order):
        return generate_receipt(order)

scene = OrderArrange().create().paid().with_receipt().arrange()
order = scene.order
receipt = scene.receipt
```

> **Note:** When multiple steps share the same label (like `"order"` above), the label always points to the latest result. Steps that need the value use injection by matching the label name in their parameter list.

### Inline steps with `.then()`

Use `.then()` to add a step without defining a method. Parameter names are matched against context labels, just like `@step` methods.

```python
def create_api_token(user):
    return Token.objects.create(user=user)

scene = (
    account_arrange
        .register()
        .verified()
        .then("token", create_api_token)
        .arrange()
)
user = scene.user
token = scene.token
```

Works with lambdas too — the parameter name is the injection key:

```python
scene = (
    account_arrange
        .register()
        .then("email", lambda user: user.email)
        .arrange()
)
```

### Teardown

Override `teardown` on your Arrange to clean up resources. This is where you handle cleanup that Django's transaction rollback can't cover — polymorphic model deletion, external service state, file cleanup.

```python
class AccountArrange(Arrange):
    @step("user")
    def register(self, email="user@example.com"):
        return register_user(email=email)

    def teardown(self, scene):
        scene.user.delete()
```

Use the context manager to guarantee teardown runs, even if the test crashes:

```python
with account_arrange.register().arrange() as scene:
    user = scene.user
    # ... test ...
# teardown runs automatically on exit
```

You can also call `scene.teardown()` manually if you prefer explicit control.

### Typed Scene

By default, `scene.user` returns `Any`. For full IDE autocomplete and type checking, declare a `SceneType` on your Arrange:

```python
from pyrrange import Arrange, Scene, step

class AccountArrange(Arrange):
    class SceneType(Scene):
        user: User
        api_client: APIClient

    @step("user")
    def register(self, email="user@example.com") -> User:
        return register_user(email=email)

    @step("api_client")
    def with_client(self, user: User) -> APIClient:
        return create_client(user)
```

When `SceneType` is declared, `.arrange()` returns an instance of that subclass. Your IDE sees `scene.user` as `User` and `scene.api_client` as `APIClient`.

`SceneType` is optional — without it, attribute access still works but returns `Any`. Both `scene.user` and `scene["user"]` are always available.

### Chain shortcuts

For common step combinations, define convenience methods on your Arrange:

```python
class AccountArrange(Arrange):
    @step("user")
    def register(self, email="user@example.com"):
        ...

    @step("user")
    def verified(self, user):
        ...

    @step("api_client")
    def with_authenticated_client(self, user):
        ...

    def authenticated(self):
        return self.register().verified().with_authenticated_client()

# In tests:
scene = account_arrange.authenticated().arrange()
```

These are plain Python methods — no framework magic.
