from __future__ import annotations

try:
    from fastapi import APIRouter, HTTPException, Request
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "agentplane service requires fastapi — install with: pip install 'agentplane-py[service]'"
    ) from exc

from agentplane.core.exceptions import PolicyNotFound, PolicyVersionError
from agentplane.core.policy import Policy, PolicyStatus
from agentplane.core.selector import Selector
from agentplane.service.schemas import (
    PolicyCreateRequest,
    PolicyListResponse,
    PolicyResponse,
    RollbackRequest,
)

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


def _policy_to_response(policy: Policy) -> PolicyResponse:
    return PolicyResponse(
        id=policy.id,
        priority=policy.priority,
        status=policy.status.value,
        description=policy.description,
        tags=policy.tags,
        conditions={},
        version=policy.version,
    )


@router.get("", response_model=PolicyListResponse)
async def list_policies(request: Request) -> PolicyListResponse:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Policy engine not available")
    policies = engine.get_policies()
    return PolicyListResponse(
        policies=[_policy_to_response(p) for p in policies],
        total=len(policies),
    )


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(body: PolicyCreateRequest, request: Request) -> PolicyResponse:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Policy engine not available")

    try:
        status = PolicyStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status!r}")

    policy = Policy(
        id=body.id,
        priority=body.priority,
        status=status,
        description=body.description,
        tags=body.tags,
        selector=Selector.all(),
    )
    engine.add_policy(policy)

    version_manager = request.app.state.version_manager
    if version_manager is not None:
        try:
            version_manager.publish(policy)
        except Exception:
            pass  # already published or manager not needed

    return _policy_to_response(policy)


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str, request: Request) -> PolicyResponse:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Policy engine not available")
    try:
        policy = engine._store.get(policy_id)
    except PolicyNotFound:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id!r} not found")
    return _policy_to_response(policy)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(policy_id: str, request: Request) -> None:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Policy engine not available")
    try:
        engine.remove_policy(policy_id)
    except PolicyNotFound:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id!r} not found")


@router.get("/{policy_id}/versions")
async def get_policy_versions(policy_id: str, request: Request) -> dict:
    version_manager = request.app.state.version_manager
    if version_manager is None:
        raise HTTPException(status_code=503, detail="Version manager not available")
    history = version_manager.history(policy_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No version history for policy {policy_id!r}")
    return {
        "policy_id": policy_id,
        "versions": [
            {
                "version": pv.version,
                "changelog": pv.changelog,
                "created_at": pv.created_at,
                "status": pv.policy.status.value,
            }
            for pv in history
        ],
        "total": len(history),
    }


@router.post("/{policy_id}/rollback", response_model=PolicyResponse)
async def rollback_policy(
    policy_id: str, body: RollbackRequest, request: Request
) -> PolicyResponse:
    engine = request.app.state.engine
    version_manager = request.app.state.version_manager
    if engine is None:
        raise HTTPException(status_code=503, detail="Policy engine not available")
    if version_manager is None:
        raise HTTPException(status_code=503, detail="Version manager not available")
    try:
        restored = version_manager.rollback(policy_id, to_version=body.to_version)
    except PolicyVersionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PolicyNotFound:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id!r} not found")

    engine.add_policy(restored)
    return _policy_to_response(restored)
