import pytest

import agentplane
from agentplane import AllowlistRule, PlugBoard, PolicyContext, PolicyEngine, Selector
from agentplane.core.policy import Policy


def make_engine_with_board():
    board = PlugBoard()
    engine = PolicyEngine(plug_board=board)
    engine.add_policy(Policy(
        id="test.p",
        selector=Selector.all(),
        blocking=[AllowlistRule(tools=["search"])],
    ))
    return engine, board


def ctx(agent_id="agent-1"):
    return PolicyContext.new(agent_id=agent_id, tenant_id="acme", tool_name="search", hookpoint="before_tool_call")


@pytest.mark.asyncio
async def test_plugged_agent_allowed():
    engine, board = make_engine_with_board()
    board.plug("agent-1")
    result = await engine.evaluate(ctx("agent-1"))
    assert result is not None


@pytest.mark.asyncio
async def test_unplugged_agent_blocked():
    engine, board = make_engine_with_board()
    board.unplug("agent-1", reason="budget exhausted", by="ops")
    with pytest.raises(agentplane.PolicyBlocked) as exc_info:
        await engine.evaluate(ctx("agent-1"))
    assert "unplugged" in str(exc_info.value)
    assert "budget exhausted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_replug_restores_access():
    engine, board = make_engine_with_board()
    board.unplug("agent-1", reason="test")
    board.plug("agent-1")
    result = await engine.evaluate(ctx("agent-1"))
    assert result is not None


def test_unplug_all_tenant():
    board = PlugBoard()
    board.register("agent-1", tenant_id="acme")
    board.register("agent-2", tenant_id="acme")
    board.register("agent-3", tenant_id="siemens")
    unplugged = board.unplug_all("acme", reason="incident")
    assert set(unplugged) == {"agent-1", "agent-2"}
    assert not board.is_plugged("agent-1")
    assert not board.is_plugged("agent-2")
    assert board.is_plugged("agent-3")


def test_unknown_agent_is_plugged_by_default():
    board = PlugBoard()
    assert board.is_plugged("unknown-agent")


def test_list_unplugged():
    board = PlugBoard()
    board.register("a1")
    board.register("a2")
    board.unplug("a1")
    unplugged = board.list_unplugged()
    assert len(unplugged) == 1
    assert unplugged[0].agent_id == "a1"
