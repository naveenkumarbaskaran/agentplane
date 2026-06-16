
import pytest


@pytest.fixture
def ctx():
    from agentplane import PolicyContext
    return PolicyContext.new(
        agent_id="test-agent",
        tenant_id="acme",
        hookpoint="before_tool_call",
        tool_name="sql_run",
        tool_inputs={"query": "SELECT 1"},
    )


@pytest.fixture
def engine():
    from agentplane import PolicyEngine
    return PolicyEngine()
