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
- Labeled results: access any step's output by name
- Sub-chain composition for complex entity graphs
- Inline steps via `.then()` for ad-hoc logic
- Teardown support for resource cleanup
- Framework-agnostic: works with Django, FastAPI, or any Python project

## Requirements

- Python 3.10+

## Installation

```bash
pip install pyrrange
```

## Usage

### Define an Arrange

Subclass `Arrange` and define `@step` methods. Each step receives the previous step's result as its first argument and returns the next result.

```python
from pyrrange import Arrange, step


class UserArrange(Arrange):
    @step("user")
    def register(self, previous, email="user@example.com", password="secret"):
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

### Use in tests

```python
def test_login(user_arrange):
    scene = user_arrange.register().arrange()
    user = scene["user"]

    response = client.post("/login", {"email": user.email, "password": "secret"})
    assert response.status_code == 200
```

Each test declares only the steps it needs:

```python
# Just a registered user
scene = user_arrange.register().arrange()

# Registered and verified
scene = user_arrange.register().verified().arrange()

# Full admin user
scene = user_arrange.register().verified().as_admin().arrange()
```

### Labels

Steps are labeled by default with the method name. Use `@step("label")` to set a custom label. Same label overwrites (latest wins).

```python
class OrderArrange(Arrange):
    @step("order")
    def create(self, previous, total=100):
        return create_order(total=total)

    @step("order")
    def paid(self, order):
        process_payment(order)
        return order

    @step("receipt")
    def with_receipt(self, order):
        return generate_receipt(order)

scene = OrderArrange().create().paid().with_receipt().arrange()
order = scene["order"]
receipt = scene["receipt"]
```

### Inline steps with `.then()`

Use `.then()` to add a step without defining a method. The function receives the previous result as its first argument.

```python
def create_api_token(user):
    return Token.objects.create(user=user)

scene = (
    user_arrange
        .register()
        .verified()
        .then("token", create_api_token)
        .arrange()
)
user = scene["user"]
token = scene["token"]
```

Works with lambdas too:

```python
scene = (
    user_arrange
        .register()
        .then("email", lambda user: user.email)
        .arrange()
)
```

### Sub-chain composition

Complex entities get their own Arrange. Parent steps execute sub-chains.

```python
class PlanArrange(Arrange):
    @step("plan")
    def starter(self, previous, price=9.99):
        return create_plan(previous, tier="starter", price=price)

    @step("plan")
    def with_addons(self, plan, addons=None):
        attach_addons(plan, addons or ["support"])
        return plan


class UserArrange(Arrange):
    @step("user")
    def register(self, previous, email="user@example.com"):
        return register_user(email=email)

    @step("user")
    def with_plan(self, user, plan_chain):
        from pyrrange import Context
        sub_ctx = Context()
        sub_ctx.set_result("_parent", user)
        plan_scene = plan_chain.bind(sub_ctx).execute()
        user.plan = plan_scene.result
        return user

scene = (
    UserArrange()
        .register()
        .with_plan(PlanArrange().starter(price=19.99).with_addons())
        .arrange()
)
```

### Teardown

Override `teardown` on your Arrange to clean up resources.

```python
class UserArrange(Arrange):
    @step("user")
    def register(self, previous, email="user@example.com"):
        return register_user(email=email)

    def teardown(self, scene):
        scene["user"].delete()

scene = user_arrange.register().arrange()
# ... test ...
scene.teardown()
```

### Context dependencies

Inject project-specific dependencies via `Context` for steps that need external resources.

```python
from pyrrange import Context

@pytest.fixture
def ctx(db_connection):
    context = Context()
    context.set("db", db_connection)
    return context

class UserArrange(Arrange):
    @step("user")
    def register(self, previous, email="user@example.com"):
        db = self.context.get("db")
        return db.execute("INSERT INTO users ...")

scene = UserArrange(ctx).register().arrange()
```

### Expose arranges as fixtures

```python
@pytest.fixture
def user_arrange():
    return UserArrange()

def test_something(user_arrange):
    scene = user_arrange.register().verified().arrange()
    user = scene["user"]
```
