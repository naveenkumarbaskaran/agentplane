"""Example 1: Basic policy — rate limit + redact + audit for a SQL agent."""

import asyncio

import agentplane
from agentplane import (
    AuditRule,
    MetricsRule,
    PolicyContext,
    PolicyEngine,
    RateRule,
    RedactRule,
    Selector,
)
from agentplane.core.policy import Policy


async def main() -> None:
    engine = PolicyEngine()

    policy = Policy(
        id="acme.sql-agent.v1",
        description="Rate limit SQL agent calls, redact sensitive fields, audit everything.",
        selector=Selector(agents=["*"], tenants=["acme"], tools=["sql_run", "sql_query"]),
        blocking=[
            RateRule(limit=50, window="1h", per="tenant", on_breach="block"),
            RedactRule(fields=["password", "api_key", "ssn", "credit_card"]),
        ],
        non_blocking=[
            AuditRule(include_inputs=True),
            MetricsRule(emit_otel=False),
        ],
        priority=100,
    )
    engine.add_policy(policy)

    ctx = PolicyContext.new(
        agent_id="sql-agent-1",
        tenant_id="acme",
        hookpoint="before_tool_call",
        tool_name="sql_run",
        tool_inputs={"query": "SELECT * FROM users", "password": "secret123"},
    )

    try:
        await engine.evaluate(ctx)
        print("✓ Policy passed — agent may proceed")
    except agentplane.PolicyBlocked as exc:
        print(f"✗ Blocked: {exc}")
    except agentplane.PolicyDegraded as exc:
        print(f"⚠ Degraded ({exc.mode}): {exc}")


if __name__ == "__main__":
    asyncio.run(main())
