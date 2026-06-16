"""Example 4: Policy decorators — enforce, policy_guard, require_policy."""

import asyncio

import agentplane
from agentplane import AllowlistRule, PolicyContext, PolicyEngine, RateRule, Selector
from agentplane.core.policy import Policy
from agentplane.engine.decorators import enforce, policy_guard, require_policy


async def main() -> None:
    engine = PolicyEngine()
    engine.add_policy(Policy(
        id="prod.finance",
        selector=Selector(agents=["finance-agent"], tenants=["acme"]),
        blocking=[
            AllowlistRule(tools=["read_ledger", "generate_report"]),
            RateRule(limit=20, window="1h"),
        ],
        priority=100,
    ))

    # @enforce — simple wrapper, raises on block
    @enforce(engine, hookpoint="before_tool_call", agent_id="finance-agent", tenant_id="acme")
    async def read_ledger(account_id: str) -> dict:
        return {"account": account_id, "balance": 10_000}

    # @policy_guard — configurable, can skip instead of raise
    @policy_guard(engine, agent_id="finance-agent", tenant_id="acme", on_block="skip")
    async def delete_record(record_id: str) -> dict:
        return {"deleted": record_id}

    # @require_policy — assert a specific policy is active
    @require_policy(engine, "prod.finance")
    async def generate_report(period: str) -> str:
        return f"Report for {period}"

    print("Testing @enforce:")
    try:
        result = await read_ledger("ACC-001")
        print(f"  ✓ read_ledger: {result}")
    except agentplane.PolicyBlocked as exc:
        print(f"  ✗ blocked: {exc}")

    print("\nTesting @policy_guard (on_block=skip):")
    result = await delete_record("REC-999")  # blocked but returns None silently
    print(f"  Result: {result!r}  (None = silently skipped)")

    print("\nTesting @require_policy:")
    try:
        report = await generate_report("Q1-2026")
        print(f"  ✓ {report}")
    except agentplane.PolicyBlocked as exc:
        print(f"  ✗ policy not active: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
