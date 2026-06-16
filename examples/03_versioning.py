"""Example 3: Policy versioning — publish, diff, rollback."""

import asyncio

import agentplane
from agentplane import (
    AllowlistRule,
    PolicyContext,
    PolicyEngine,
    RateRule,
    RedactRule,
    Selector,
    VersionManager,
)
from agentplane.core.policy import Policy


async def main() -> None:
    vm = VersionManager()
    engine = PolicyEngine()

    # Publish v1
    policy_v1 = Policy(
        id="acme.data-access",
        selector=Selector(tenants=["acme"]),
        blocking=[
            AllowlistRule(tools=["read_file", "search"]),
            RateRule(limit=100, window="1h"),
        ],
        version=1,
    )
    vm.publish(policy_v1, changelog="Initial policy")
    engine.add_policy(policy_v1)
    print(f"Published: {policy_v1}")

    # Publish v2 — add redaction, tighten rate limit
    policy_v2 = Policy(
        id="acme.data-access",
        selector=Selector(tenants=["acme"]),
        blocking=[
            AllowlistRule(tools=["read_file", "search"]),
            RateRule(limit=50, window="1h"),     # tighter
            RedactRule(fields=["ssn", "api_key"]),  # new
        ],
        version=2,
    )
    vm.publish(policy_v2, changelog="Tighten rate limit, add redaction")
    engine.add_policy(policy_v2)
    print(f"Published: {policy_v2}")

    # Diff v1 → v2
    diff = vm.diff("acme.data-access", 1, 2)
    print(f"\nDiff v1 → v2:")
    print(f"  Added blocking rules:   {diff.added_blocking}")
    print(f"  Removed blocking rules: {diff.removed_blocking}")

    # Rollback to v1
    restored = vm.rollback("acme.data-access", to_version=1)
    engine.add_policy(restored)
    print(f"\nRolled back to: {restored}")

    # Show full history
    history = vm.history("acme.data-access")
    print(f"\nVersion history ({len(history)} versions):")
    for v in history:
        print(f"  v{v.version}: {v.changelog}")


if __name__ == "__main__":
    asyncio.run(main())
