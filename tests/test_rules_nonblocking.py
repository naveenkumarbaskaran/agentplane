import pytest

from agentplane import PolicyContext
from agentplane.rules.nonblocking import AlertRule, AuditRule, CostTrackingRule, MetricsRule


def ctx(**kwargs):
    defaults = dict(agent_id="a1", tenant_id="acme", hookpoint="before_tool_call")
    return PolicyContext.new(**{**defaults, **kwargs})


@pytest.mark.asyncio
async def test_audit_rule_runs():
    rule = AuditRule(include_inputs=True, include_outputs=False)
    await rule.evaluate(ctx(tool_inputs={"query": "SELECT 1"}))


@pytest.mark.asyncio
async def test_alert_rule_log():
    rule = AlertRule(channel="log")
    await rule.evaluate(ctx())


@pytest.mark.asyncio
async def test_cost_tracking_accumulates():
    rule = CostTrackingRule(track_per="tenant")
    c = ctx(cost_usd=0.05)
    await rule.evaluate(c)
    await rule.evaluate(c)
    total = rule.get_total("acme")
    assert abs(total - 0.10) < 1e-9


@pytest.mark.asyncio
async def test_metrics_rule_counts():
    rule = MetricsRule(emit_otel=False)
    c = ctx()
    await rule.evaluate(c)
    await rule.evaluate(c)
    key = "a1:before_tool_call"
    assert rule._counts.get(key, 0) == 2
