import pytest

import agentplane
from agentplane import AllowlistRule, PolicyEngine, Selector
from agentplane.core.policy import Policy
from agentplane.engine.decorators import enforce, policy_guard, require_policy


def make_engine():
    engine = PolicyEngine()
    engine.add_policy(Policy(
        id="test.deco",
        selector=Selector(agents=["test-agent"], tenants=["acme"]),
        blocking=[AllowlistRule(tools=["allowed_fn"])],
        priority=100,
    ))
    return engine


@pytest.mark.asyncio
async def test_enforce_allows():
    engine = make_engine()

    @enforce(engine, hookpoint="before_tool_call", agent_id="test-agent", tenant_id="acme")
    async def allowed_fn():
        return "ok"

    result = await allowed_fn()
    assert result == "ok"


@pytest.mark.asyncio
async def test_enforce_blocks():
    engine = make_engine()

    @enforce(engine, hookpoint="before_tool_call", agent_id="test-agent", tenant_id="acme")
    async def blocked_fn():
        return "should not reach"

    with pytest.raises(agentplane.PolicyBlocked):
        await blocked_fn()


@pytest.mark.asyncio
async def test_policy_guard_skip_on_block():
    engine = make_engine()

    @policy_guard(engine, agent_id="test-agent", tenant_id="acme", on_block="skip")
    async def blocked_fn():
        return "should not reach"

    result = await blocked_fn()
    assert result is None


@pytest.mark.asyncio
async def test_require_policy_passes_when_active():
    engine = make_engine()

    @require_policy(engine, "test.deco")
    async def some_fn():
        return "ok"

    result = await some_fn()
    assert result == "ok"


@pytest.mark.asyncio
async def test_require_policy_blocks_when_missing():
    engine = PolicyEngine()

    @require_policy(engine, "nonexistent.policy")
    async def some_fn():
        return "ok"

    with pytest.raises(agentplane.PolicyBlocked):
        await some_fn()
