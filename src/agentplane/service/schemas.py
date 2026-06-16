from __future__ import annotations

try:
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "agentplane service requires pydantic — install with: pip install 'agentplane-py[service]'"
    ) from exc

from typing import Any


class PolicyResponse(BaseModel):
    id: str
    priority: int
    status: str
    description: str
    tags: dict[str, str]
    conditions: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class PolicyListResponse(BaseModel):
    policies: list[PolicyResponse]
    total: int


class AgentStatusResponse(BaseModel):
    agent_id: str
    plugged: bool
    degradation_mode: str | None


class AuditEntry(BaseModel):
    ts: float
    policy_id: str = Field(alias="policy.id", default="")
    policy_rule: str = Field(alias="policy.rule", default="")
    policy_status: str = Field(alias="policy.status", default="")
    policy_reason: str = Field(alias="policy.reason", default="")
    policy_duration_ms: float = Field(alias="policy.duration_ms", default=0.0)
    agent_id: str = ""
    tenant_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    hookpoint: str | None = None
    tool_name: str | None = None

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    status: str
    version: str


class RollbackRequest(BaseModel):
    to_version: int


class UnplugRequest(BaseModel):
    reason: str
    by: str


class PolicyCreateRequest(BaseModel):
    id: str
    priority: int = 100
    status: str = "active"
    description: str = ""
    tags: dict[str, str] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
