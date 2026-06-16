from __future__ import annotations

from dataclasses import dataclass, field

from agentplane.core.context import PolicyContext


@dataclass
class Selector:
    """Defines what a policy targets.

    All conditions are AND-ed. Within each list, any match qualifies (OR).
    Wildcards: "*" matches everything for that dimension.

    Examples::

        Selector(agents=["*"])                         # all agents
        Selector(tenants=["acme"], tools=["sql_run"])  # acme tenant + sql tool only
        Selector(hookpoints=["before_tool_call"], tags={"env": "prod"})
    """

    agents: list[str] = field(default_factory=lambda: ["*"])
    tenants: list[str] = field(default_factory=lambda: ["*"])
    hookpoints: list[str] = field(default_factory=lambda: ["*"])
    tools: list[str] = field(default_factory=lambda: ["*"])
    tags: dict[str, str] = field(default_factory=dict)

    def matches(self, ctx: PolicyContext) -> bool:
        if not self._match_list(self.agents, ctx.agent_id):
            return False
        if not self._match_list(self.tenants, ctx.tenant_id or ""):
            return False
        if ctx.hookpoint and not self._match_list(self.hookpoints, ctx.hookpoint):
            return False
        if ctx.tool_name and not self._match_list(self.tools, ctx.tool_name):
            return False
        for k, v in self.tags.items():
            if ctx.tags.get(k) != v:
                return False
        return True

    @staticmethod
    def _match_list(patterns: list[str], value: str) -> bool:
        for p in patterns:
            if p == "*" or p == value:
                return True
        return False

    @classmethod
    def all(cls) -> Selector:
        return cls()
