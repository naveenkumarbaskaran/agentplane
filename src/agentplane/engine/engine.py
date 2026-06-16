from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from agentplane.audit.trail import AuditTrail, get_default_audit
from agentplane.core.context import PolicyContext
from agentplane.core.exceptions import PolicyBlocked, PolicyDegraded
from agentplane.core.policy import ConflictResolution, Policy
from agentplane.core.rule import BlockingRule, NonBlockingRule, RuleResult, RuleVerdict
from agentplane.degradation.modes import DegradationConfig, DegradationMode, DegradationTracker
from agentplane.engine.plugboard import PlugBoard
from agentplane.store.memory import InMemoryPolicyStore

logger = logging.getLogger("agentplane.engine")


class PolicyEngine:
    """The enforcement core — evaluates all matching policies for a given context.

    The engine is designed to be embedded in-process with every agent. It:
    - Loads policies from a store (memory or SQLite)
    - Syncs from a remote service when configured
    - Evaluates blocking rules synchronously (agent waits)
    - Fires non-blocking rules asynchronously (agent never waits)
    - Tracks degradation state with automatic recovery
    - Records every decision to the audit trail

    Conflict resolution:
    - Default: most restrictive verdict wins
    - Override: highest priority policy wins when explicitly set

    Usage (standalone)::

        engine = PolicyEngine()
        engine.add_policy(my_policy)
        result = await engine.evaluate(ctx)

    Usage (with agenthooks)::

        engine = PolicyEngine()
        engine.add_policy(my_policy)
        engine.attach(registry)          # registers hook impls automatically
    """

    def __init__(
        self,
        store: Any | None = None,
        audit: AuditTrail | None = None,
        on_offline: str = "use_cache",
        plug_board: PlugBoard | None = None,
    ) -> None:
        self._store = store or InMemoryPolicyStore()
        self._audit = audit or get_default_audit()
        self._on_offline = on_offline
        self._degradation = DegradationTracker()
        self._plug_board = plug_board or PlugBoard()
        self._sync_task: asyncio.Task | None = None  # type: ignore[type-arg]

    def add_policy(self, policy: Policy) -> None:
        self._store.save(policy)
        logger.info("agentplane.engine policy_added id=%s v%d", policy.id, policy.version)

    def remove_policy(self, policy_id: str) -> None:
        self._store.delete(policy_id)

    def get_policies(self) -> list[Policy]:
        return self._store.list_active()

    async def evaluate(self, ctx: PolicyContext) -> PolicyContext:
        """Evaluate all matching policies for the given context.

        Blocking rules are evaluated synchronously in priority order.
        Non-blocking rules are fired as background tasks.
        Raises PolicyBlocked or PolicyDegraded on enforcement.
        """
        # Check plug state — hard lockout before any policy evaluation
        if not self._plug_board.is_plugged(ctx.agent_id):
            slot = self._plug_board.get_slot(ctx.agent_id)
            reason = slot.unplugged_reason if slot else "agent is unplugged"
            raise PolicyBlocked("plugboard", "unplug", f"agent {ctx.agent_id!r} is unplugged: {reason}")

        # Check degradation state first
        if self._degradation.is_degraded(ctx.agent_id):
            mode = self._degradation.get_mode(ctx.agent_id)
            self._degradation.get_config(ctx.agent_id)
            logger.warning(
                "agentplane.engine degraded agent=%s mode=%s",
                ctx.agent_id, mode,
            )
            if mode == DegradationMode.FULL_BLOCK:
                raise PolicyDegraded("engine", mode.value if mode else "", "agent is degraded")

        policies = self._match_policies(ctx)
        if not policies:
            return ctx

        t0 = time.monotonic()
        blocking_results: list[tuple[Policy, BlockingRule, RuleResult]] = []

        # Evaluate all blocking rules across all matching policies
        for policy in policies:
            for rule in sorted(policy.blocking, key=lambda r: r.priority):
                try:
                    result = await rule.evaluate(ctx)
                    blocking_results.append((policy, rule, result))
                    await self._audit.record(
                        policy_id=policy.id,
                        rule=rule.name or type(rule).__name__,
                        ctx=ctx,
                        status=result.verdict.value,
                        reason=result.reason,
                        duration_ms=(time.monotonic() - t0) * 1000,
                    )
                except (PolicyBlocked, PolicyDegraded):
                    raise
                except Exception as exc:
                    logger.error(
                        "agentplane.engine rule_error policy=%s rule=%s error=%s",
                        policy.id, type(rule).__name__, exc,
                    )

        # Resolve conflicts and enforce
        ctx = await self._resolve_and_enforce(ctx, policies, blocking_results)

        # Fire non-blocking rules as background tasks
        for policy in policies:
            for nb_rule in policy.non_blocking:
                asyncio.ensure_future(self._run_non_blocking(nb_rule, ctx, policy.id))

        return ctx

    async def _resolve_and_enforce(
        self,
        ctx: PolicyContext,
        policies: list[Policy],
        results: list[tuple[Policy, BlockingRule, RuleResult]],
    ) -> PolicyContext:
        # Collect all non-allow verdicts
        blocks = [(p, r, res) for p, r, res in results if res.verdict == RuleVerdict.BLOCK]
        degrades = [(p, r, res) for p, r, res in results if res.verdict == RuleVerdict.DEGRADE]
        escalates = [(p, r, res) for p, r, res in results if res.verdict == RuleVerdict.ESCALATE]

        # Check if any policy explicitly overrides via priority
        priority_override = None
        for p, r, res in results:
            if p.conflict_resolution == ConflictResolution.PRIORITY:
                priority_override = (p, r, res)
                break

        if priority_override:
            p, r, res = priority_override
            if res.verdict == RuleVerdict.BLOCK:
                raise PolicyBlocked(p.id, r.name or type(r).__name__, res.reason)
            if res.verdict == RuleVerdict.DEGRADE:
                mode = res.metadata.get("mode", "read_only")
                self._degradation.degrade(ctx.agent_id, DegradationConfig(
                    mode=DegradationMode(mode), reason=res.reason
                ))
                raise PolicyDegraded(p.id, mode, res.reason)
            return ctx

        # Most restrictive: block > degrade > escalate > allow
        if blocks:
            p, r, res = blocks[0]
            raise PolicyBlocked(p.id, r.name or type(r).__name__, res.reason)

        if degrades:
            p, r, res = degrades[0]
            mode = res.metadata.get("mode", "read_only")
            self._degradation.degrade(ctx.agent_id, DegradationConfig(
                mode=DegradationMode(mode), reason=res.reason
            ))
            raise PolicyDegraded(p.id, mode, res.reason)

        if escalates:
            p, r, res = escalates[0]
            if p.escalation:
                await p.escalation.escalate(ctx, trigger="rule_escalation")

        return ctx

    async def _run_non_blocking(
        self, rule: NonBlockingRule, ctx: PolicyContext, policy_id: str
    ) -> None:
        try:
            await rule.evaluate(ctx)
        except Exception as exc:
            logger.debug(
                "agentplane.engine non_blocking_error policy=%s rule=%s error=%s",
                policy_id, type(rule).__name__, exc,
            )

    def _match_policies(self, ctx: PolicyContext) -> list[Policy]:
        policies = self._store.list_active()
        matched = [p for p in policies if p.selector.matches(ctx)]
        return sorted(matched, key=lambda p: -p.priority)

    def attach(self, registry: Any) -> None:
        """Attach to an agenthooks HookRegistry — registers evaluation as hook impls."""
        try:
            from agentplane.engine._hooks import register_hooks
            register_hooks(self, registry)
            logger.info("agentplane.engine attached to agenthooks registry")
        except ImportError:
            logger.warning("agentplane.engine agenthooks not installed — attach() skipped")

    def degrade(self, agent_id: str, mode: DegradationMode, reason: str = "", recover_after: str = "30m") -> None:
        self._degradation.degrade(agent_id, DegradationConfig(
            mode=mode, reason=reason, recover_after=recover_after,
        ))

    def recover(self, agent_id: str) -> None:
        self._degradation.recover(agent_id)

    def is_degraded(self, agent_id: str) -> bool:
        return self._degradation.is_degraded(agent_id)

    @classmethod
    def from_file(cls, path: str) -> PolicyEngine:
        """Load policies from a JSON file (offline mode)."""
        import json

        from agentplane.store.memory import InMemoryPolicyStore
        from agentplane.store.sqlite import _dict_to_policy
        store = InMemoryPolicyStore()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("policies", []):
            store.save(_dict_to_policy(item))
        engine = cls(store=store)
        logger.info("agentplane.engine loaded %d policies from %s", store.count(), path)
        return engine
