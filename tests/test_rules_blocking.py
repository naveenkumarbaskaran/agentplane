import pytest

from agentplane import PolicyContext
from agentplane.core.rule import RuleVerdict
from agentplane.rules.blocking import (
    AllowlistRule,
    CostBudgetRule,
    DenylistRule,
    RateRule,
    RedactRule,
    RequireTenantRule,
    TokenBudgetRule,
)


def ctx(**kwargs):
    defaults = dict(agent_id="a1", tenant_id="acme", hookpoint="before_tool_call")
    return PolicyContext.new(**{**defaults, **kwargs})


@pytest.mark.asyncio
async def test_allowlist_allows():
    rule = AllowlistRule(tools=["search", "read_file"])
    result = await rule.evaluate(ctx(tool_name="search"))
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_allowlist_blocks():
    rule = AllowlistRule(tools=["search"])
    result = await rule.evaluate(ctx(tool_name="delete_db"))
    assert result.verdict == RuleVerdict.BLOCK


@pytest.mark.asyncio
async def test_allowlist_wildcard():
    rule = AllowlistRule(tools=["*"])
    result = await rule.evaluate(ctx(tool_name="anything"))
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_allowlist_no_tool():
    rule = AllowlistRule(tools=["search"])
    result = await rule.evaluate(ctx())
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_denylist_blocks():
    rule = DenylistRule(tools=["delete_db"])
    result = await rule.evaluate(ctx(tool_name="delete_db"))
    assert result.verdict == RuleVerdict.BLOCK


@pytest.mark.asyncio
async def test_denylist_allows():
    rule = DenylistRule(tools=["delete_db"])
    result = await rule.evaluate(ctx(tool_name="search"))
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_redact_returns_allow():
    rule = RedactRule(fields=["ssn", "api_key"])
    result = await rule.evaluate(ctx())
    assert result.verdict == RuleVerdict.ALLOW
    assert "ssn" in result.metadata.get("redacted_fields", [])


@pytest.mark.asyncio
async def test_rate_rule_allows_under_limit():
    rule = RateRule(limit=5, window="1h", per="tenant")
    c = ctx()
    for _ in range(5):
        result = await rule.evaluate(c)
        assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_rate_rule_blocks_over_limit():
    rule = RateRule(limit=3, window="1h", per="tenant")
    c = ctx()
    for _ in range(3):
        await rule.evaluate(c)
    result = await rule.evaluate(c)
    assert result.verdict == RuleVerdict.BLOCK


@pytest.mark.asyncio
async def test_require_tenant_allows():
    rule = RequireTenantRule(tenants=["acme", "siemens"])
    result = await rule.evaluate(ctx(tenant_id="acme"))
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_require_tenant_blocks():
    rule = RequireTenantRule(tenants=["acme"])
    result = await rule.evaluate(ctx(tenant_id="unknown"))
    assert result.verdict == RuleVerdict.BLOCK


@pytest.mark.asyncio
async def test_token_budget_allows():
    rule = TokenBudgetRule(max_tokens=1000, window="1d")
    result = await rule.evaluate(ctx(token_count=100))
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_token_budget_blocks():
    rule = TokenBudgetRule(max_tokens=100, window="1d")
    c = ctx(token_count=60)
    await rule.evaluate(c)
    result = await rule.evaluate(c)
    assert result.verdict == RuleVerdict.BLOCK


@pytest.mark.asyncio
async def test_cost_budget_allows():
    rule = CostBudgetRule(max_usd=10.0, window="1d")
    result = await rule.evaluate(ctx(cost_usd=0.5))
    assert result.verdict == RuleVerdict.ALLOW


@pytest.mark.asyncio
async def test_cost_budget_blocks():
    rule = CostBudgetRule(max_usd=1.0, window="1d")
    c = ctx(cost_usd=0.6)
    await rule.evaluate(c)
    result = await rule.evaluate(c)
    assert result.verdict == RuleVerdict.BLOCK
