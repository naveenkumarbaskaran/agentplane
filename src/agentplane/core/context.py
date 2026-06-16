from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PolicyContext:
    """Runtime context passed to every rule evaluation.

    Carries identity, routing, and observability fields so rules can make
    decisions without reaching into agent internals.
    """

    agent_id: str
    tenant_id: str | None = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hookpoint: str | None = None
    tool_name: str | None = None
    tool_inputs: dict[str, Any] = field(default_factory=dict)
    tool_result: dict[str, Any] | None = None
    llm_response: str | None = None
    token_count: int = 0
    cost_usd: float = 0.0
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def new(
        cls,
        agent_id: str,
        tenant_id: str | None = None,
        **kwargs: Any,
    ) -> PolicyContext:
        return cls(agent_id=agent_id, tenant_id=tenant_id, **kwargs)

    def enrich(self, key: str, value: Any) -> PolicyContext:
        from dataclasses import replace
        new_meta = {**self.metadata, key: value}
        return replace(self, metadata=new_meta)
