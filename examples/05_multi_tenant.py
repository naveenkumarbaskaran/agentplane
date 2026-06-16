"""Example 5: Multi-tenant — different policies per tenant, conflict resolution."""

import asyncio

import agentplane
from agentplane import (
    AllowlistRule,
    AuditRule,
    CostBudgetRule,
    PolicyContext,
    PolicyEngine,
    RateRule,
    RedactRule,
    RequireTenantRule,
    Selector,
    TokenBudgetRule,
)
from agentplane.core.policy import ConflictResolution, Policy
from agentplane.rules.api import ApiAllowlistRule, ApiDenylistRule
from agentplane.security.scanner import InjectionScanRule, PIIScanRule


async def main() -> None:
    engine = PolicyEngine()

    # Global policy — applies to all agents
    engine.add_policy(Policy(
        id="global.security",
        selector=Selector(agents=["*"], tenants=["*"]),
        blocking=[
            InjectionScanRule(on_detection="block"),
            RedactRule(fields=["ssn", "api_key", "password", "credit_card"]),
        ],
        non_blocking=[AuditRule(), PIIScanRule()],
        priority=300,
    ))

    # ACME tenant — strict limits
    engine.add_policy(Policy(
        id="acme.prod",
        selector=Selector(tenants=["acme"]),
        blocking=[
            RateRule(limit=100, window="1h", per="tenant"),
            TokenBudgetRule(max_tokens=50_000, window="1d"),
            CostBudgetRule(max_usd=10.0, window="1d"),
            AllowlistRule(tools=["search", "read_file", "summarize"]),
            ApiDenylistRule(paths=["/admin/*", "/internal/*"]),
        ],
        priority=200,
    ))

    # SIEMENS tenant — relaxed limits, more tools
    engine.add_policy(Policy(
        id="siemens.prod",
        selector=Selector(tenants=["siemens"]),
        blocking=[
            RateRule(limit=500, window="1h", per="tenant"),
            TokenBudgetRule(max_tokens=200_000, window="1d"),
            AllowlistRule(tools=["*"]),
            ApiAllowlistRule(paths=["/api/*"], methods=["GET", "POST"]),
        ],
        priority=200,
    ))

    tenants = [
        ("acme", "search", {"query": "quarterly revenue"}),
        ("acme", "delete_db", {}),
        ("siemens", "run_simulation", {}),
        ("unknown_tenant", "search", {}),
    ]

    for tenant, tool, inputs in tenants:
        ctx = PolicyContext.new(
            agent_id="multi-agent-1",
            tenant_id=tenant,
            hookpoint="before_tool_call",
            tool_name=tool,
            tool_inputs=inputs,
            cost_usd=0.001,
            token_count=100,
        )
        try:
            await engine.evaluate(ctx)
            print(f"✓ tenant={tenant!r:12} tool={tool!r:15} → allowed")
        except agentplane.PolicyBlocked as exc:
            print(f"✗ tenant={tenant!r:12} tool={tool!r:15} → blocked: {exc.reason[:60]}")
        except agentplane.PolicyDegraded as exc:
            print(f"⚠ tenant={tenant!r:12} tool={tool!r:15} → degraded ({exc.mode})")


if __name__ == "__main__":
    asyncio.run(main())
