"""Example 2: Escalation chain — from alert → HITL → block."""

import asyncio

import agentplane
from agentplane import (
    Alert,
    Block,
    Degrade,
    EscalationChain,
    EscalationLevel,
    PolicyContext,
    PolicyEngine,
    RateRule,
    Selector,
)
from agentplane.core.policy import Policy


async def main() -> None:
    engine = PolicyEngine()

    escalation = EscalationChain([
        EscalationLevel(
            level=1,
            trigger="rate_breach",
            action=Alert(channel="log", message="Rate limit approaching"),
        ),
        EscalationLevel(
            level=2,
            trigger="rate_breach",
            action=Degrade(mode="rate_throttle", recover_after="10m"),
        ),
        EscalationLevel(
            level=3,
            trigger="rate_breach",
            action=Block(reason="Repeated rate limit violations"),
        ),
    ])

    policy = Policy(
        id="acme.billing-agent.v1",
        selector=Selector(agents=["billing-agent"], tenants=["acme"]),
        blocking=[
            RateRule(limit=10, window="1m", per="tenant", on_breach="escalate"),
        ],
        escalation=escalation,
        priority=200,
    )
    engine.add_policy(policy)

    ctx = PolicyContext.new(
        agent_id="billing-agent",
        tenant_id="acme",
        hookpoint="before_tool_call",
        tool_name="charge_card",
    )

    # Simulate multiple calls to trigger escalation
    for i in range(15):
        try:
            await engine.evaluate(ctx)
            print(f"Call {i+1}: ✓ allowed")
        except agentplane.PolicyBlocked as exc:
            print(f"Call {i+1}: ✗ blocked — {exc}")
            break
        except agentplane.PolicyDegraded as exc:
            print(f"Call {i+1}: ⚠ degraded ({exc.mode}) — {exc}")
            break


if __name__ == "__main__":
    asyncio.run(main())
