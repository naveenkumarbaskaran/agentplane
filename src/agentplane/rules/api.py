from __future__ import annotations

from agentplane.core.context import PolicyContext
from agentplane.core.rule import BlockingRule, RuleResult


class ApiAllowlistRule(BlockingRule):
    """Block API calls not in the allowlist (by path and/or method).

    Usage::

        ApiAllowlistRule(paths=["/api/v1/read", "/api/v1/search"])
        ApiAllowlistRule(paths=["/api/*"], methods=["GET", "HEAD"])
    """

    name = "api_allowlist"

    def __init__(
        self,
        paths: list[str] | None = None,
        methods: list[str] | None = None,
        on_violation: str = "block",
        priority: int = 100,
    ) -> None:
        self.paths = paths or ["*"]
        self.methods = [m.upper() for m in (methods or ["*"])]
        self.on_violation = on_violation
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        api_path = ctx.metadata.get("api_path")
        api_method = ctx.metadata.get("api_method", "").upper()
        if not api_path:
            return RuleResult.allow()
        if not self._match_path(api_path):
            reason = f"API path {api_path!r} not in allowlist"
            if self.on_violation == "degrade":
                return RuleResult.degrade("safe_tools_only", reason)
            return RuleResult.block(reason)
        if "*" not in self.methods and api_method and api_method not in self.methods:
            reason = f"API method {api_method!r} not in allowlist {self.methods}"
            return RuleResult.block(reason)
        return RuleResult.allow()

    def _match_path(self, path: str) -> bool:
        for pattern in self.paths:
            if pattern == "*":
                return True
            if pattern.endswith("*") and path.startswith(pattern[:-1]):
                return True
            if pattern == path:
                return True
        return False


class ApiDenylistRule(BlockingRule):
    """Block specific API paths/methods explicitly.

    Usage::

        ApiDenylistRule(paths=["/admin/*", "/internal/*"])
        ApiDenylistRule(paths=["/api/delete"], methods=["DELETE", "POST"])
    """

    name = "api_denylist"

    def __init__(
        self,
        paths: list[str],
        methods: list[str] | None = None,
        priority: int = 200,
    ) -> None:
        self.paths = paths
        self.methods = [m.upper() for m in (methods or ["*"])]
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        api_path = ctx.metadata.get("api_path")
        api_method = ctx.metadata.get("api_method", "").upper()
        if not api_path:
            return RuleResult.allow()
        if ApiAllowlistRule._match_path(self, api_path):  # type: ignore[arg-type]
            if "*" in self.methods or not api_method or api_method in self.methods:
                return RuleResult.block(f"API path {api_path!r} is denied")
        return RuleResult.allow()

    def _match_path(self, path: str) -> bool:
        for pattern in self.paths:
            if pattern == "*":
                return True
            if pattern.endswith("*") and path.startswith(pattern[:-1]):
                return True
            if pattern == path:
                return True
        return False
