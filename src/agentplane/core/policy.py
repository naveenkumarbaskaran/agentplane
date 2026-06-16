from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from agentplane.core.rule import BlockingRule, NonBlockingRule
from agentplane.core.selector import Selector
from agentplane.escalation.chain import EscalationChain


class PolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class ConflictResolution(StrEnum):
    MOST_RESTRICTIVE = "most_restrictive"
    PRIORITY = "priority"


@dataclass
class Policy:
    """The atomic unit of agentplane — a versioned, targeted behavioral policy.

    Policies are attached to agents via selectors. At runtime the PolicyEngine
    evaluates all matching policies, resolves conflicts, and enforces decisions
    via agenthooks hookpoints.

    Usage::

        policy = Policy(
            id="acme.data-access",
            selector=Selector(tenants=["acme"], tools=["sql_run"]),
            blocking=[RedactRule(fields=["ssn"]), RateRule(limit=100, window="1h")],
            non_blocking=[AuditRule(), AlertRule(channel="slack", on="breach")],
            escalation=EscalationChain([...]),
            priority=100,
        )
    """

    id: str
    selector: Selector = field(default_factory=Selector.all)
    blocking: list[BlockingRule] = field(default_factory=list)
    non_blocking: list[NonBlockingRule] = field(default_factory=list)
    escalation: EscalationChain | None = None
    priority: int = 100
    conflict_resolution: ConflictResolution = ConflictResolution.MOST_RESTRICTIVE
    status: PolicyStatus = PolicyStatus.ACTIVE
    version: int = 1
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == PolicyStatus.ACTIVE

    def bump_version(self) -> Policy:
        from dataclasses import replace
        return replace(self, version=self.version + 1, updated_at=time.time())

    def deprecate(self) -> Policy:
        from dataclasses import replace
        return replace(self, status=PolicyStatus.DEPRECATED, updated_at=time.time())

    def retire(self) -> Policy:
        from dataclasses import replace
        return replace(self, status=PolicyStatus.RETIRED, updated_at=time.time())

    def activate(self) -> Policy:
        from dataclasses import replace
        return replace(self, status=PolicyStatus.ACTIVE, updated_at=time.time())

    def __repr__(self) -> str:
        return (
            f"Policy(id={self.id!r}, v{self.version}, "
            f"status={self.status.value}, "
            f"blocking={len(self.blocking)}, non_blocking={len(self.non_blocking)})"
        )
