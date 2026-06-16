from __future__ import annotations

import json
import logging
import time
from typing import Any

from agentplane.core.context import PolicyContext
from agentplane.core.rule import NonBlockingRule

logger = logging.getLogger("agentplane.rules")


class AuditRule(NonBlockingRule):
    """Append an audit entry for every policy evaluation."""

    name = "audit"

    def __init__(
        self,
        include_inputs: bool = True,
        include_outputs: bool = False,
    ) -> None:
        self.include_inputs = include_inputs
        self.include_outputs = include_outputs

    async def evaluate(self, ctx: PolicyContext) -> None:
        entry: dict[str, Any] = {
            "ts": time.time(),
            "agent_id": ctx.agent_id,
            "tenant_id": ctx.tenant_id,
            "session_id": ctx.session_id,
            "trace_id": ctx.trace_id,
            "hookpoint": ctx.hookpoint,
            "tool_name": ctx.tool_name,
        }
        if self.include_inputs and ctx.tool_inputs:
            entry["tool_inputs"] = ctx.tool_inputs
        if self.include_outputs and ctx.tool_result:
            entry["tool_result"] = ctx.tool_result
        logger.info("agentplane.audit %s", json.dumps(entry, default=str))


class AlertRule(NonBlockingRule):
    """Emit an alert on a condition. Fire-and-forget."""

    name = "alert"

    def __init__(
        self,
        channel: str = "log",
        on: str = "breach",
        webhook_url: str | None = None,
    ) -> None:
        self.channel = channel
        self.on = on
        self.webhook_url = webhook_url

    async def evaluate(self, ctx: PolicyContext) -> None:
        msg = (
            f"[agentplane.alert] agent={ctx.agent_id} tenant={ctx.tenant_id} "
            f"hookpoint={ctx.hookpoint} tool={ctx.tool_name}"
        )
        if self.channel == "log":
            logger.warning(msg)
        elif self.channel == "webhook" and self.webhook_url:
            await self._post_webhook(msg, ctx)

    async def _post_webhook(self, msg: str, ctx: PolicyContext) -> None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    self.webhook_url,  # type: ignore[arg-type]
                    json={"text": msg, "agent_id": ctx.agent_id, "tenant_id": ctx.tenant_id},
                )
        except Exception as exc:
            logger.debug("agentplane.alert webhook failed: %s", exc)


class CostTrackingRule(NonBlockingRule):
    """Track cumulative cost per agent/tenant — non-blocking observation."""

    name = "cost_tracking"

    def __init__(self, track_per: str = "tenant") -> None:
        self.track_per = track_per
        self._totals: dict[str, float] = {}

    async def evaluate(self, ctx: PolicyContext) -> None:
        key = ctx.tenant_id or ctx.agent_id if self.track_per == "tenant" else ctx.agent_id
        self._totals[key] = self._totals.get(key, 0.0) + ctx.cost_usd
        logger.debug(
            "agentplane.cost key=%s total_usd=%.6f delta_usd=%.6f",
            key, self._totals[key], ctx.cost_usd,
        )

    def get_total(self, key: str) -> float:
        return self._totals.get(key, 0.0)


class MetricsRule(NonBlockingRule):
    """Emit OTel metrics for every policy evaluation. Zero-dep fallback included."""

    name = "metrics"

    def __init__(self, emit_otel: bool = True) -> None:
        self.emit_otel = emit_otel
        self._counts: dict[str, int] = {}

    async def evaluate(self, ctx: PolicyContext) -> None:
        key = f"{ctx.agent_id}:{ctx.hookpoint or 'unknown'}"
        self._counts[key] = self._counts.get(key, 0) + 1
        if self.emit_otel:
            try:
                from opentelemetry import metrics as _metrics
                meter = _metrics.get_meter("agentplane", "0.1.0")
                counter = meter.create_counter("agentplane.policy.evaluations")
                counter.add(1, {"agent_id": ctx.agent_id, "hookpoint": ctx.hookpoint or ""})
            except ImportError:
                pass
