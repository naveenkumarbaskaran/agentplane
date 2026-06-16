from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from agentplane.core.context import PolicyContext
from agentplane.escalation.actions import HITL, Alert, Block, Degrade, EscalationAction

logger = logging.getLogger("agentplane.escalation")


@dataclass
class EscalationEvent:
    level: int
    trigger: str
    action: EscalationAction
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class EscalationLevel:
    level: int
    trigger: str
    action: EscalationAction
    cooldown_s: float = 300.0


class EscalationChain:
    """Stateful, time-aware escalation chain.

    Unlike a simple if/else — this tracks history. An agent that breaches
    a limit 3 times in 10 minutes escalates further than one that breached
    once a week ago.

    Usage::

        chain = EscalationChain([
            EscalationLevel(1, trigger="rate_breach",   action=Alert(channel="slack")),
            EscalationLevel(2, trigger="repeat_breach", action=HITL(timeout="5m")),
            EscalationLevel(3, trigger="hitl_timeout",  action=Block()),
        ])
        await chain.escalate(ctx, trigger="rate_breach")
    """

    def __init__(self, levels: list[EscalationLevel]) -> None:
        self._levels = sorted(levels, key=lambda l: l.level)
        self._history: list[EscalationEvent] = []
        self._current_level: int = 0

    @property
    def current_level(self) -> int:
        return self._current_level

    def recent_count(self, trigger: str, window_s: float = 600.0) -> int:
        now = time.time()
        return sum(
            1 for e in self._history
            if e.trigger == trigger and (now - e.timestamp) < window_s
        )

    async def escalate(self, ctx: PolicyContext, trigger: str) -> EscalationAction | None:
        matching = [l for l in self._levels if l.trigger == trigger]
        if not matching:
            matching = self._levels

        count = self.recent_count(trigger)
        level_idx = min(count, len(matching) - 1)
        level = matching[level_idx]

        event = EscalationEvent(
            level=level.level,
            trigger=trigger,
            action=level.action,
        )
        self._history.append(event)
        self._current_level = level.level

        logger.warning(
            "agentplane.escalation agent=%s tenant=%s trigger=%s level=%d action=%s",
            ctx.agent_id, ctx.tenant_id, trigger, level.level, type(level.action).__name__,
        )

        await self._execute(ctx, level.action, event)
        return level.action

    async def _execute(
        self, ctx: PolicyContext, action: EscalationAction, event: EscalationEvent
    ) -> None:
        from agentplane.core.exceptions import PolicyBlocked, PolicyDegraded

        if isinstance(action, Block):
            raise PolicyBlocked("escalation", "chain", action.reason)

        elif isinstance(action, Degrade):
            raise PolicyDegraded("escalation", action.mode, action.reason)

        elif isinstance(action, Alert):
            logger.warning(
                "agentplane.escalation.alert channel=%s agent=%s tenant=%s msg=%s",
                action.channel, ctx.agent_id, ctx.tenant_id, action.message or event.trigger,
            )
            if action.channel == "webhook" and action.webhook_url:
                await self._post_webhook(action, ctx)

        elif isinstance(action, HITL):
            approved = await self._wait_hitl(ctx, action)
            if not approved:
                fallback_action = Block(reason=f"HITL timeout after {action.timeout}")
                await self._execute(ctx, fallback_action, event)
            else:
                event.resolved = True

    async def _wait_hitl(self, ctx: PolicyContext, action: HITL) -> bool:
        logger.warning(
            "agentplane.hitl agent=%s tenant=%s timeout=%s — awaiting approval",
            ctx.agent_id, ctx.tenant_id, action.timeout,
        )
        try:
            await asyncio.sleep(action.timeout_seconds())
            return False
        except asyncio.CancelledError:
            return True

    async def _post_webhook(self, action: Alert, ctx: PolicyContext) -> None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    action.webhook_url,  # type: ignore[arg-type]
                    json={"agent_id": ctx.agent_id, "tenant_id": ctx.tenant_id},
                )
        except Exception as exc:
            logger.debug("agentplane.escalation webhook failed: %s", exc)

    def reset(self) -> None:
        self._current_level = 0
        self._history.clear()

    def history(self) -> list[EscalationEvent]:
        return list(self._history)
