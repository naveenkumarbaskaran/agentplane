from __future__ import annotations

import functools
import logging
from typing import Any

from agentplane.core.context import PolicyContext
from agentplane.core.exceptions import PolicyBlocked, PolicyDegraded

logger = logging.getLogger("agentplane.decorators")


def enforce(engine: Any, *, hookpoint: str = "call", agent_id: str = "default", tenant_id: str | None = None) -> Any:
    """Decorator — wrap any async function with policy enforcement.

    Usage::

        engine = PolicyEngine()
        engine.add_policy(my_policy)

        @enforce(engine, hookpoint="before_tool_call", agent_id="my-agent")
        async def run_sql(query: str) -> str:
            ...

        # Or as a context manager:
        async with policy_scope(engine, ctx) as enforced_ctx:
            ...
    """
    def decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = PolicyContext.new(
                agent_id=agent_id,
                tenant_id=tenant_id,
                hookpoint=hookpoint,
                tool_name=fn.__name__,
                tool_inputs={"args": str(args), "kwargs": str(kwargs)},
            )
            await engine.evaluate(ctx)
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


def policy_guard(
    engine: Any,
    *,
    agent_id: str,
    tenant_id: str | None = None,
    hookpoint: str = "call",
    on_block: str = "raise",
    on_degrade: str = "raise",
) -> Any:
    """Decorator with configurable block/degrade handling.

    on_block:   "raise" (default) | "skip" (return None) | "log"
    on_degrade: "raise" (default) | "skip" | "log"

    Usage::

        @policy_guard(engine, agent_id="billing-agent", tenant_id="acme", on_block="skip")
        async def charge_card(amount: float) -> dict:
            ...
    """
    def decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = PolicyContext.new(
                agent_id=agent_id,
                tenant_id=tenant_id,
                hookpoint=hookpoint,
                tool_name=fn.__name__,
                tool_inputs={"args": str(args)},
            )
            try:
                await engine.evaluate(ctx)
            except PolicyBlocked as exc:
                if on_block == "raise":
                    raise
                logger.warning("agentplane.guard blocked fn=%s reason=%s", fn.__name__, exc)
                return None
            except PolicyDegraded as exc:
                if on_degrade == "raise":
                    raise
                logger.warning("agentplane.guard degraded fn=%s mode=%s", fn.__name__, exc.mode)
                return None
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


def require_policy(engine: Any, policy_id: str) -> Any:
    """Decorator — assert a specific policy is active before calling the function.

    Usage::

        @require_policy(engine, "acme.data-access")
        async def export_data() -> bytes:
            ...
    """
    def decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            policies = engine.get_policies()
            ids = {p.id for p in policies}
            if policy_id not in ids:
                raise PolicyBlocked(policy_id, "require_policy", f"policy {policy_id!r} not active")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
