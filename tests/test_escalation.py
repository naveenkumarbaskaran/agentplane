import pytest

import agentplane
from agentplane import Alert, Block, Degrade, EscalationChain, EscalationLevel, PolicyContext


def ctx():
    return PolicyContext.new(agent_id="a1", tenant_id="acme", hookpoint="before_tool_call")


@pytest.mark.asyncio
async def test_escalation_alert_does_not_raise():
    chain = EscalationChain([
        EscalationLevel(1, trigger="breach", action=Alert(channel="log")),
    ])
    result = await chain.escalate(ctx(), trigger="breach")
    assert isinstance(result, Alert)


@pytest.mark.asyncio
async def test_escalation_block_raises():
    chain = EscalationChain([
        EscalationLevel(1, trigger="breach", action=Block(reason="test block")),
    ])
    with pytest.raises(agentplane.PolicyBlocked):
        await chain.escalate(ctx(), trigger="breach")


@pytest.mark.asyncio
async def test_escalation_degrade_raises():
    chain = EscalationChain([
        EscalationLevel(1, trigger="breach", action=Degrade(mode="read_only")),
    ])
    with pytest.raises(agentplane.PolicyDegraded):
        await chain.escalate(ctx(), trigger="breach")


@pytest.mark.asyncio
async def test_escalation_progresses_with_history():
    chain = EscalationChain([
        EscalationLevel(1, trigger="breach", action=Alert(channel="log")),
        EscalationLevel(2, trigger="breach", action=Degrade(mode="rate_throttle")),
        EscalationLevel(3, trigger="breach", action=Block(reason="too many")),
    ])
    c = ctx()
    await chain.escalate(c, trigger="breach")  # level 1 — alert
    assert chain.current_level == 1

    try:
        await chain.escalate(c, trigger="breach")  # level 2 — degrade
    except agentplane.PolicyDegraded:
        pass

    with pytest.raises(agentplane.PolicyBlocked):
        await chain.escalate(c, trigger="breach")  # level 3 — block


def test_escalation_reset():
    chain = EscalationChain([
        EscalationLevel(1, trigger="b", action=Alert(channel="log")),
    ])
    chain.reset()
    assert chain.current_level == 0
    assert chain.history() == []
