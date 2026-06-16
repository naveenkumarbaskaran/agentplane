import pytest

import agentplane
from agentplane import (
    AllowlistRule,
    AuditRule,
    PolicyContext,
    PolicyEngine,
    RateRule,
    Selector,
)
from agentplane.core.policy import Policy


def make_policy(**kwargs):
    defaults = dict(
        id="test.policy",
        selector=Selector(tenants=["acme"]),
        blocking=[AllowlistRule(tools=["search", "read_file"])],
        non_blocking=[AuditRule()],
        priority=100,
    )
    return Policy(**{**defaults, **kwargs})


def ctx(**kwargs):
    defaults = dict(agent_id="a1", tenant_id="acme", hookpoint="before_tool_call", tool_name="search")
    return PolicyContext.new(**{**defaults, **kwargs})


@pytest.mark.asyncio
async def test_engine_allows_matching_tool():
    engine = PolicyEngine()
    engine.add_policy(make_policy())
    result = await engine.evaluate(ctx(tool_name="search"))
    assert result is not None


@pytest.mark.asyncio
async def test_engine_blocks_denied_tool():
    engine = PolicyEngine()
    engine.add_policy(make_policy())
    with pytest.raises(agentplane.PolicyBlocked):
        await engine.evaluate(ctx(tool_name="delete_db"))


@pytest.mark.asyncio
async def test_engine_no_matching_policy_allows():
    engine = PolicyEngine()
    engine.add_policy(make_policy(selector=Selector(tenants=["other"])))
    result = await engine.evaluate(ctx(tenant_id="acme"))
    assert result is not None


@pytest.mark.asyncio
async def test_engine_multiple_policies_most_restrictive():
    engine = PolicyEngine()
    engine.add_policy(Policy(
        id="p1",
        selector=Selector(tenants=["acme"]),
        blocking=[AllowlistRule(tools=["search"])],
        priority=100,
    ))
    engine.add_policy(Policy(
        id="p2",
        selector=Selector(tenants=["acme"]),
        blocking=[RateRule(limit=1, window="1h")],
        priority=50,
    ))
    # First call passes
    await engine.evaluate(ctx(tool_name="search"))
    # Second call blocked by rate limit
    with pytest.raises(agentplane.PolicyBlocked):
        await engine.evaluate(ctx(tool_name="search"))


@pytest.mark.asyncio
async def test_engine_degrade_and_recover():
    from agentplane.degradation.modes import DegradationMode
    engine = PolicyEngine()
    engine.degrade("a1", DegradationMode.READ_ONLY, reason="test")
    assert engine.is_degraded("a1")
    engine.recover("a1")
    assert not engine.is_degraded("a1")


@pytest.mark.asyncio
async def test_engine_remove_policy():
    engine = PolicyEngine()
    engine.add_policy(make_policy())
    engine.remove_policy("test.policy")
    result = await engine.evaluate(ctx(tool_name="delete_db"))
    assert result is not None
