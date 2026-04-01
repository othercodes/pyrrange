from __future__ import annotations

import pytest

from pyrrange.arrange import Arrange, StepError, step
from pyrrange.context import Context
from pyrrange.scene import Scene

# --- Test Arrange classes (simulating host project) ---


class CounterArrange(Arrange):
    """Simple arrange for testing step mechanics."""

    @step
    def add(self, previous, value: int = 1):
        current = previous or 0
        return current + value

    @step
    def multiply(self, previous, factor: int = 2):
        return previous * factor

    @step
    def noop(self, previous):
        return previous


class UserArrange(Arrange):
    """Simulates a real-world UserArrange for integration testing."""

    @step
    def register(self, previous, email: str = "test@example.com"):
        return {"type": "user", "email": email, "verified": False, "plans": []}

    @step
    def verified(self, user):
        user["verified"] = True
        return user

    @step("plan")
    def with_plan(self, user, plan_chain: Arrange):
        sub_ctx = Context()
        sub_ctx.set_result("_parent", user)
        plan_result = plan_chain.bind(sub_ctx).execute()
        plan = plan_result.result
        user["plans"].append(plan)
        return user


class PlanArrange(Arrange):
    """Simulates a PlanArrange sub-chain."""

    @step("plan")
    def shared(self, previous, price: float = 9.99):
        user = previous
        return {"type": "plan", "proxy_type": "shared", "price": price, "user_email": user["email"]}

    @step("plan")
    def dedicated(self, previous, price: float = 19.99):
        user = previous
        return {"type": "plan", "proxy_type": "dedicated", "price": price, "user_email": user["email"]}

    @step
    def with_replacements(self, plan, total: int = 10):
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

    def test_step_preserves_args(self) -> None:
        chain = CounterArrange().add(42)
        assert chain._recorded_steps[0].args == (42,)

    def test_step_preserves_kwargs(self) -> None:
        chain = CounterArrange().add(value=42)
        assert chain._recorded_steps[0].kwargs == {"value": 42}

    def test_empty_chain_has_no_steps(self) -> None:
        chain = CounterArrange()
        assert len(chain._recorded_steps) == 0


class TestStepLabels:
    def test_default_label_is_method_name(self) -> None:
        chain = CounterArrange().add(5)
        assert chain._recorded_steps[0].label == "add"

    def test_custom_label(self) -> None:
        chain = UserArrange().with_plan(PlanArrange().shared())
        assert chain._recorded_steps[0].label == "plan"

    def test_keyword_label(self) -> None:
        class KeywordArrange(Arrange):
            @step(label="custom")
            def do_thing(self, previous):
                return "done"

        scene = KeywordArrange().do_thing().arrange()
        assert scene["custom"] == "done"

    def test_labels_accessible_after_arrange(self) -> None:
        scene = CounterArrange().add(5).multiply(3).arrange()
        assert scene["add"] == 5
        assert scene["multiply"] == 15

    def test_custom_label_accessible_after_arrange(self) -> None:
        scene = UserArrange().register().with_plan(PlanArrange().shared(price=5.99)).arrange()
        assert scene["register"]["type"] == "user"
        # "plan" label on with_plan returns the user (parent step returns user)
        assert scene["plan"]["type"] == "user"
        # The plan is inside user["plans"]
        assert scene["plan"]["plans"][0]["type"] == "plan"

    def test_same_label_overwrites(self) -> None:
        scene = UserArrange().register().verified().arrange()
        # register and verified share the same dict (Python mutability),
        # so both reflect the final state
        assert scene["register"]["verified"] is True
        assert scene["verified"]["verified"] is True


class TestExecution:
    def test_execute_runs_steps_in_order(self) -> None:
        scene = CounterArrange().add(5).multiply(3).arrange()
        assert scene.result == 15

    def test_arrange_returns_context(self) -> None:
        scene = CounterArrange().add(5).arrange()
        assert isinstance(scene, Scene)

    def test_context_result_is_last_step(self) -> None:
        scene = CounterArrange().add(5).multiply(3).arrange()
        assert scene.result == 15

    def test_execute_empty_chain_returns_context(self) -> None:
        scene = CounterArrange().arrange()
        assert isinstance(scene, Scene)
        assert scene.result is None

    def test_noop_preserves_result(self) -> None:
        scene = CounterArrange().add(7).noop().arrange()
        assert scene.result == 7

    def test_first_step_receives_none(self) -> None:
        class CheckArrange(Arrange):
            @step
            def check(self, previous):
                assert previous is None
                return "ok"

        scene = CheckArrange().check().arrange()
        assert scene["check"] == "ok"

    def test_second_step_receives_first_result(self) -> None:
        class CheckArrange(Arrange):
            @step
            def first(self, previous):
                return "hello"

            @step
            def second(self, previous):
                return previous.upper()

        scene = CheckArrange().first().second().arrange()
        assert scene["second"] == "HELLO"


class TestThen:
    def test_then_receives_previous_result(self) -> None:
        scene = CounterArrange().add(5).then("doubled", lambda x: x * 2).arrange()
        assert scene["doubled"] == 10

    def test_then_with_none_previous(self) -> None:
        scene = Arrange().then("start", lambda prev: "hello").arrange()
        assert scene["start"] == "hello"

    def test_then_chains_with_steps(self) -> None:
        scene = CounterArrange().add(10).then("formatted", lambda n: f"value={n}").arrange()
        assert scene["add"] == 10
        assert scene["formatted"] == "value=10"

    def test_then_with_named_function(self) -> None:
        def double_it(previous):
            return previous * 2

        scene = CounterArrange().add(5).then("doubled", double_it).arrange()
        assert scene["doubled"] == 10

    def test_then_with_extra_args(self) -> None:
        def multiply(previous, factor):
            return previous * factor

        scene = CounterArrange().add(5).then("result", multiply, 3).arrange()
        assert scene["result"] == 15

    def test_then_with_extra_kwargs(self) -> None:
        def multiply(previous, factor=2):
            return previous * factor

        scene = CounterArrange().add(5).then("result", multiply, factor=4).arrange()
        assert scene["result"] == 20

    def test_then_returns_self_for_chaining(self) -> None:
        chain = Arrange()
        result = chain.then("x", lambda p: p)
        assert result is chain

    def test_then_error_wrapped_in_step_error(self) -> None:
        def bad_fn(previous):
            raise ValueError("boom")

        with pytest.raises(StepError, match="'fail'") as exc_info:
            Arrange().then("fail", bad_fn).arrange()
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert str(exc_info.value.__cause__) == "boom"

    def test_then_simulates_authenticated_client(self) -> None:
        """Real-world pattern: create infrastructure from parent entity."""

        def create_client(user):
            return {"type": "client", "token": f"token-for-{user['email']}"}

        scene = UserArrange().register(email="test@example.com").verified().then("api_client", create_client).arrange()
        assert scene["api_client"]["token"] == "token-for-test@example.com"
        assert scene["verified"]["verified"] is True


class TestContextIntegration:
    def test_steps_access_dependencies(self) -> None:
        class DepArrange(Arrange):
            @step
            def use_dep(self, previous):
                make_thing = self.context.get("make_thing")
                return make_thing("hello")

        ctx = Context()
        ctx.set("make_thing", lambda x: x.upper())
        scene = DepArrange(ctx).use_dep().arrange()
        assert scene["use_dep"] == "HELLO"

    def test_missing_dependency_raises_during_execution(self) -> None:
        class DepArrange(Arrange):
            @step
            def use_dep(self, previous):
                return self.context.get("missing")

        ctx = Context()
        with pytest.raises(StepError, match="use_dep") as exc_info:
            DepArrange(ctx).use_dep().arrange()
        assert isinstance(exc_info.value.__cause__, LookupError)


class TestSubChainComposition:
    def test_sub_chain_receives_parent_context(self) -> None:
        scene = UserArrange().register(email="sub@test.com").with_plan(PlanArrange().shared(price=5.99)).arrange()
        user = scene["register"]
        assert user["plans"][0]["user_email"] == "sub@test.com"

    def test_sub_chain_result_attached_to_parent(self) -> None:
        scene = UserArrange().register().with_plan(PlanArrange().shared(price=5.99)).arrange()
        user = scene["register"]
        assert len(user["plans"]) == 1
        assert user["plans"][0]["price"] == 5.99

    def test_multiple_sub_chains(self) -> None:
        scene = (
            UserArrange()
            .register()
            .verified()
            .with_plan(PlanArrange().shared(price=9.99))
            .with_plan(PlanArrange().dedicated(price=19.99))
            .arrange()
        )
        user = scene["register"]
        assert len(user["plans"]) == 2
        assert user["plans"][0]["proxy_type"] == "shared"
        assert user["plans"][1]["proxy_type"] == "dedicated"

    def test_sub_chain_with_multiple_steps(self) -> None:
        scene = (
            UserArrange().register().with_plan(PlanArrange().shared(price=9.99).with_replacements(total=20)).arrange()
        )
        user = scene["register"]
        assert user["plans"][0]["replacements"] == 20

    def test_parent_result_restored_after_sub_chain(self) -> None:
        scene = UserArrange().register(email="parent@test.com").with_plan(PlanArrange().shared()).verified().arrange()
        # verified() should operate on the user, not the plan
        assert scene["verified"]["verified"] is True
        assert scene["verified"]["email"] == "parent@test.com"


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

    def test_bind_then_arrange(self) -> None:
        chain = CounterArrange().add(5).multiply(3)
        ctx = Context()
        scene = chain.bind(ctx).arrange()
        assert scene.result == 15


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
