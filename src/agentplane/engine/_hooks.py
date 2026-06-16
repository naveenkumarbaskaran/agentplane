from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("agentplane.engine.hooks")


def register_hooks(engine: Any, registry: Any) -> None:
    """Register PolicyEngine.evaluate as agenthooks hook implementations."""

    @registry.implement("before_tool_call", fallback=True, timeout_ms=1000)
    async def _agentplane_before_tool(ctx: Any) -> Any:
        from agentplane.core.context import PolicyContext
        pctx = PolicyContext.new(
            agent_id=getattr(ctx, "session_id", "unknown"),
            tenant_id=getattr(ctx, "tenant_id", None),
            session_id=getattr(ctx, "session_id", ""),
            trace_id=getattr(ctx, "trace_id", ""),
            hookpoint="before_tool_call",
            tool_name=getattr(ctx, "tool_name", None),
            tool_inputs=getattr(ctx, "tool_inputs", {}),
            tags=getattr(ctx, "metadata", {}).get("tags", {}),
        )
        await engine.evaluate(pctx)
        return ctx

    @registry.implement("after_llm_response", fallback=True, timeout_ms=500)
    async def _agentplane_after_llm(ctx: Any) -> Any:
        from agentplane.core.context import PolicyContext
        pctx = PolicyContext.new(
            agent_id=getattr(ctx, "session_id", "unknown"),
            tenant_id=getattr(ctx, "tenant_id", None),
            hookpoint="after_llm_response",
            llm_response=getattr(ctx, "llm_response", None),
        )
        await engine.evaluate(pctx)
        return ctx
