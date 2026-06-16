from __future__ import annotations

from agentplane.core.context import PolicyContext
from agentplane.core.rule import BlockingRule, RuleResult, RuleVerdict


class AllowlistRule(BlockingRule):
    """Block execution if the tool being called is not in the allowlist."""

    name = "allowlist"

    def __init__(
        self,
        tools: list[str],
        on_violation: str = "block",
        priority: int = 100,
    ) -> None:
        self.tools = frozenset(tools)
        self.on_violation = on_violation
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        if not ctx.tool_name:
            return RuleResult.allow()
        if ctx.tool_name in self.tools or "*" in self.tools:
            return RuleResult.allow(f"tool {ctx.tool_name!r} in allowlist")
        reason = f"tool {ctx.tool_name!r} not in allowlist {sorted(self.tools)}"
        if self.on_violation == "degrade":
            return RuleResult.degrade("safe_tools_only", reason)
        if self.on_violation == "escalate":
            return RuleResult.escalate(1, reason)
        return RuleResult.block(reason)


class DenylistRule(BlockingRule):
    """Block execution if the tool being called is in the denylist."""

    name = "denylist"

    def __init__(self, tools: list[str], priority: int = 200) -> None:
        self.tools = frozenset(tools)
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        if not ctx.tool_name:
            return RuleResult.allow()
        if ctx.tool_name in self.tools:
            return RuleResult.block(f"tool {ctx.tool_name!r} is denied")
        return RuleResult.allow()


class RedactRule(BlockingRule):
    """Mark sensitive fields as redacted in audit and downstream context."""

    name = "redact"

    def __init__(self, fields: list[str], priority: int = 50) -> None:
        self.fields = list(fields)
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        return RuleResult(
            verdict=RuleVerdict.ALLOW,
            reason="redacted",
            metadata={"redacted_fields": self.fields},
        )


class RateRule(BlockingRule):
    """In-memory sliding-window rate limiter per agent/tenant/session."""

    name = "rate_limit"

    def __init__(
        self,
        limit: int = 100,
        window: str = "1h",
        per: str = "tenant",
        on_breach: str = "block",
        priority: int = 100,
    ) -> None:
        self.limit = limit
        self.window_s = self._parse_window(window)
        self.per = per
        self.on_breach = on_breach
        self.priority = priority
        self._windows: dict[str, list[float]] = {}

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        import time
        key = self._key(ctx)
        now = time.monotonic()
        self._windows.setdefault(key, [])
        self._windows[key] = [t for t in self._windows[key] if now - t < self.window_s]
        if len(self._windows[key]) >= self.limit:
            reason = f"rate limit exceeded: {self.limit} calls per {self.window_s}s for {self.per}={key}"
            if self.on_breach == "escalate":
                return RuleResult.escalate(1, reason)
            if self.on_breach == "degrade":
                return RuleResult.degrade("rate_throttle", reason)
            return RuleResult.block(reason)
        self._windows[key].append(now)
        return RuleResult.allow()

    def _key(self, ctx: PolicyContext) -> str:
        if self.per == "tenant":
            return ctx.tenant_id or ctx.agent_id
        if self.per == "session":
            return ctx.session_id
        return ctx.agent_id

    @staticmethod
    def _parse_window(w: str) -> float:
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        if w[-1] in units:
            return float(w[:-1]) * units[w[-1]]
        return float(w)


class RequireTenantRule(BlockingRule):
    """Block if ctx.tenant_id is not in the allowed set."""

    name = "require_tenant"

    def __init__(self, tenants: list[str], priority: int = 150) -> None:
        self.tenants = frozenset(tenants)
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        if ctx.tenant_id in self.tenants:
            return RuleResult.allow()
        return RuleResult.block(
            f"tenant {ctx.tenant_id!r} not in allowed set {sorted(self.tenants)}"
        )


class TokenBudgetRule(BlockingRule):
    """Block if cumulative token usage exceeds budget within the window."""

    name = "token_budget"

    def __init__(
        self,
        max_tokens: int,
        window: str = "1d",
        per: str = "tenant",
        on_breach: str = "block",
        priority: int = 100,
    ) -> None:
        self.max_tokens = max_tokens
        self.window_s = RateRule._parse_window(window)
        self.per = per
        self.on_breach = on_breach
        self.priority = priority
        self._usage: dict[str, list[tuple[float, int]]] = {}

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        import time
        key = ctx.tenant_id or ctx.agent_id if self.per == "tenant" else ctx.agent_id
        now = time.monotonic()
        self._usage.setdefault(key, [])
        self._usage[key] = [(t, n) for t, n in self._usage[key] if now - t < self.window_s]
        used = sum(n for _, n in self._usage[key])
        if used + ctx.token_count > self.max_tokens:
            reason = f"token budget exceeded: {used + ctx.token_count} > {self.max_tokens}"
            if self.on_breach == "degrade":
                return RuleResult.degrade("rate_throttle", reason)
            return RuleResult.block(reason)
        self._usage[key].append((now, ctx.token_count))
        return RuleResult.allow()


class CostBudgetRule(BlockingRule):
    """Block if cumulative cost (USD) exceeds budget within the window."""

    name = "cost_budget"

    def __init__(
        self,
        max_usd: float,
        window: str = "1d",
        per: str = "tenant",
        on_breach: str = "block",
        priority: int = 100,
    ) -> None:
        self.max_usd = max_usd
        self.window_s = RateRule._parse_window(window)
        self.per = per
        self.on_breach = on_breach
        self.priority = priority
        self._usage: dict[str, list[tuple[float, float]]] = {}

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        import time
        key = ctx.tenant_id or ctx.agent_id if self.per == "tenant" else ctx.agent_id
        now = time.monotonic()
        self._usage.setdefault(key, [])
        self._usage[key] = [(t, c) for t, c in self._usage[key] if now - t < self.window_s]
        spent = sum(c for _, c in self._usage[key])
        if spent + ctx.cost_usd > self.max_usd:
            reason = f"cost budget exceeded: ${spent + ctx.cost_usd:.4f} > ${self.max_usd}"
            if self.on_breach == "degrade":
                return RuleResult.degrade("rate_throttle", reason)
            return RuleResult.block(reason)
        self._usage[key].append((now, ctx.cost_usd))
        return RuleResult.allow()
