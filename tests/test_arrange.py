from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, step
from pyrrange.context import Context

# --- Test Arrange classes (simulating host project) ---


class CounterArrange(Arrange):
    """Simple arrange for testing step mechanics."""

    @step
    def add(self, value: int = 1):
        current = self.context.result or 0
        return current + value

    @step
    def multiply(self, factor: int = 2):
        return self.context.result * factor

    @step
    def noop(self):
        return self.context.result


class UserArrange(Arrange):
    """Simulates a real-world UserArrange for integration testing."""

    @step
    def register(self, email: str = "test@example.com"):
        return {"type": "user", "email": email, "verified": False, "plans": []}

    @step
    def verified(self):
        user = self.context.result
        user["verified"] = True
        return user

    @step
    def with_plan(self, plan_chain: Arrange):
        user = self.context.result
        plan = plan_chain.bind(self.context).execute()
        user["plans"].append(plan)
        return user


class PlanArrange(Arrange):
    """Simulates a PlanArrange sub-chain."""

    @step
    def shared(self, price: float = 9.99):
        user = self.context.result
        return {"type": "plan", "proxy_type": "shared", "price": price, "user_email": user["email"]}

    @step
    def dedicated(self, price: float = 19.99):
        user = self.context.result
        return {"type": "plan", "proxy_type": "dedicated", "price": price, "user_email": user["email"]}

    @step
    def with_replacements(self, total: int = 10):
        plan = self.context.result
        plan["replacements"] = total
        return plan


# --- Tests ---


class TestStepRecording:
    def test_step_records_without_executing(self) -> None:
        chain = CounterArrange().add(5)
        assert len(chain._recorded_steps) == 1
        assert chain.context.result is None  # not executed

    def test_multiple_steps_record_in_order(self) -> None:
        chain = CounterArrange().add(5).multiply(3).noop()
        assert len(chain._recorded_steps) == 3

    def test_step_returns_self_for_chaining(self) -> None:
        chain = CounterArrange()
        result = chain.add(1)
        assert result is chain

    def test_step_preserves_args_and_kwargs(self) -> None:
        chain = CounterArrange().add(42)
        _fn, args, _kwargs = chain._recorded_steps[0]
        assert args == (42,)

    def test_step_preserves_kwargs(self) -> None:
        chain = CounterArrange().add(value=42)
        _fn, _args, kwargs = chain._recorded_steps[0]
        assert kwargs == {"value": 42}

    def test_empty_chain_has_no_steps(self) -> None:
        chain = CounterArrange()
        assert len(chain._recorded_steps) == 0


class TestExecution:
    def test_execute_runs_steps_in_order(self) -> None:
        ctx = Context()
        result = CounterArrange(ctx).add(5).multiply(3).execute()
        assert result == 15

    def test_result_property_triggers_execution(self) -> None:
        ctx = Context()
        result = CounterArrange(ctx).add(5).multiply(3).result
        assert result == 15

    def test_context_result_updated_after_each_step(self) -> None:
        ctx = Context()
        CounterArrange(ctx).add(5).multiply(3).execute()
        assert ctx.results == [5, 15]

    def test_execute_empty_chain_returns_none(self) -> None:
        ctx = Context()
        result = CounterArrange(ctx).execute()
        assert result is None

    def test_noop_preserves_result(self) -> None:
        ctx = Context()
        result = CounterArrange(ctx).add(7).noop().result
        assert result == 7


class TestContextIntegration:
    def test_steps_access_dependencies(self) -> None:
        class DepArrange(Arrange):
            @step
            def use_dep(self):
                make_thing = self.context.get("make_thing")
                return make_thing("hello")

        ctx = Context()
        ctx.set("make_thing", lambda x: x.upper())
        result = DepArrange(ctx).use_dep().result
        assert result == "HELLO"

    def test_missing_dependency_raises_during_execution(self) -> None:
        from pyrrange.arrange import StepError

        class DepArrange(Arrange):
            @step
            def use_dep(self):
                return self.context.get("missing")

        ctx = Context()
        with pytest.raises(StepError, match="use_dep") as exc_info:
            _result = DepArrange(ctx).use_dep().result
        assert isinstance(exc_info.value.__cause__, LookupError)


class TestSubChainComposition:
    def test_sub_chain_receives_parent_context(self) -> None:
        ctx = Context()
        user = UserArrange(ctx).register(email="sub@test.com").with_plan(PlanArrange().shared(price=5.99)).result
        assert user["plans"][0]["user_email"] == "sub@test.com"

    def test_sub_chain_result_attached_to_parent(self) -> None:
        ctx = Context()
        user = UserArrange(ctx).register().with_plan(PlanArrange().shared(price=5.99)).result
        assert len(user["plans"]) == 1
        assert user["plans"][0]["price"] == 5.99

    def test_multiple_sub_chains(self) -> None:
        ctx = Context()
        user = (
            UserArrange(ctx)
            .register()
            .verified()
            .with_plan(PlanArrange().shared(price=9.99))
            .with_plan(PlanArrange().dedicated(price=19.99))
            .result
        )
        assert len(user["plans"]) == 2
        assert user["plans"][0]["proxy_type"] == "shared"
        assert user["plans"][1]["proxy_type"] == "dedicated"

    def test_sub_chain_with_multiple_steps(self) -> None:
        ctx = Context()
        user = (
            UserArrange(ctx).register().with_plan(PlanArrange().shared(price=9.99).with_replacements(total=20)).result
        )
        assert user["plans"][0]["replacements"] == 20

    def test_parent_result_restored_after_sub_chain(self) -> None:
        ctx = Context()
        user = UserArrange(ctx).register(email="parent@test.com").with_plan(PlanArrange().shared()).verified().result
        # verified() should operate on the user, not the plan
        assert user["verified"] is True
        assert user["email"] == "parent@test.com"


class TestBind:
    def test_bind_sets_context(self) -> None:
        chain = CounterArrange().add(5)
        ctx = Context()
        chain.bind(ctx)
        assert chain.context is ctx

    def test_bind_returns_self(self) -> None:
        chain = CounterArrange().add(5)
        ctx = Context()
        result = chain.bind(ctx)
        assert result is chain

    def test_bind_then_execute(self) -> None:
        chain = CounterArrange().add(5).multiply(3)
        ctx = Context()
        result = chain.bind(ctx).result
        assert result == 15


class TestCopy:
    def test_copy_creates_independent_chain(self) -> None:
        original = CounterArrange().add(5)
        copied = original.copy()
        copied.add(10)
        assert len(original._recorded_steps) == 1
        assert len(copied._recorded_steps) == 2

    def test_copy_does_not_share_context(self) -> None:
        ctx = Context()
        original = CounterArrange(ctx)
        copied = original.copy()
        assert copied.context is not ctx
