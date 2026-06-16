from __future__ import annotations

try:
    from fastapi import APIRouter, HTTPException, Request
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "agentplane service requires fastapi — install with: pip install 'agentplane-py[service]'"
    ) from exc

from agentplane.service.schemas import (
    AgentStatusResponse,
    PolicyListResponse,
    UnplugRequest,
)
from agentplane.service.routes.policies import _policy_to_response

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("/{agent_id}/policies", response_model=PolicyListResponse)
async def list_agent_policies(agent_id: str, request: Request) -> PolicyListResponse:
    """List active policies matching this agent — used by PolicySyncer."""
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Policy engine not available")

    from agentplane.core.context import PolicyContext

    ctx = PolicyContext.new(agent_id=agent_id)
    all_policies = engine._match_policies(ctx)
    return PolicyListResponse(
        policies=[_policy_to_response(p) for p in all_policies],
        total=len(all_policies),
    )


@router.post("/{agent_id}/plug", status_code=200)
async def plug_agent(agent_id: str, request: Request) -> dict:
    plug_board = request.app.state.plug_board
    if plug_board is None:
        raise HTTPException(status_code=503, detail="PlugBoard not available")
    plug_board.plug(agent_id)
    return {"agent_id": agent_id, "plugged": True}


@router.post("/{agent_id}/unplug", status_code=200)
async def unplug_agent(agent_id: str, body: UnplugRequest, request: Request) -> dict:
    plug_board = request.app.state.plug_board
    if plug_board is None:
        raise HTTPException(status_code=503, detail="PlugBoard not available")
    plug_board.unplug(agent_id, reason=body.reason, by=body.by)
    return {"agent_id": agent_id, "plugged": False, "reason": body.reason, "by": body.by}


@router.get("/{agent_id}/status", response_model=AgentStatusResponse)
async def agent_status(agent_id: str, request: Request) -> AgentStatusResponse:
    plug_board = request.app.state.plug_board
    engine = request.app.state.engine

    plugged = True
    if plug_board is not None:
        plugged = plug_board.is_plugged(agent_id)

    degradation_mode: str | None = None
    if engine is not None and engine.is_degraded(agent_id):
        mode = engine._degradation.get_mode(agent_id)
        degradation_mode = mode.value if mode else None

    return AgentStatusResponse(
        agent_id=agent_id,
        plugged=plugged,
        degradation_mode=degradation_mode,
    )
