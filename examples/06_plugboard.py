"""Example 6: Plug/Unplug — hard lockout and restore for agents."""

import asyncio

import agentplane
from agentplane import (
    AllowlistRule,
    CostBudgetRule,
    PlugBoard,
    PolicyContext,
    PolicyEngine,
    RateRule,
    Selector,
)
from agentplane.core.policy import Policy


async def main() -> None:
    # Create a shared plug board — can be used across multiple engines
    board = PlugBoard()
    engine = PolicyEngine(plug_board=board)

    engine.add_policy(Policy(
        id="prod.billing",
        selector=Selector(agents=["billing-agent"], tenants=["acme"]),
        blocking=[
            AllowlistRule(tools=["charge_card", "refund", "read_balance"]),
            CostBudgetRule(max_usd=100.0, window="1d", on_breach="block"),
            RateRule(limit=50, window="1h"),
        ],
        priority=100,
    ))

    # Register and plug the agent
    board.register("billing-agent", tenant_id="acme", tags={"tier": "premium"})

    ctx = PolicyContext.new(
        agent_id="billing-agent",
        tenant_id="acme",
        hookpoint="before_tool_call",
        tool_name="charge_card",
    )

    # Normal operation
    await engine.evaluate(ctx)
    print("✓ billing-agent: plugged — charge_card allowed")

    # Agent runs out of budget — ops unplugs it
    board.unplug("billing-agent", reason="daily cost budget exhausted", by="ops-team")
    print("⚡ billing-agent: unplugged by ops-team")

    try:
        await engine.evaluate(ctx)
        print("This should not print")
    except agentplane.PolicyBlocked as exc:
        print(f"✗ billing-agent: {exc}")

    # Ops restores access after midnight budget reset
    board.plug("billing-agent")
    await engine.evaluate(ctx)
    print("✓ billing-agent: re-plugged — access restored")

    # --- Tenant-wide lockout ---
    board.register("invoice-agent", tenant_id="acme")
    board.register("report-agent", tenant_id="acme")
    board.register("other-agent", tenant_id="siemens")

    unplugged = board.unplug_all("acme", reason="security incident", by="security-team")
    print(f"\n⚡ Tenant lockout: {len(unplugged)} acme agents unplugged: {unplugged}")

    for agent_id in ["billing-agent", "invoice-agent", "report-agent"]:
        print(f"  {agent_id}: plugged={board.is_plugged(agent_id)}")
    print(f"  other-agent (siemens): plugged={board.is_plugged('other-agent')}")


if __name__ == "__main__":
    asyncio.run(main())
