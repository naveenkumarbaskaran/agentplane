from __future__ import annotations

import json

try:
    from fastapi import APIRouter, HTTPException, Query, Request
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "agentplane service requires fastapi — install with: pip install 'agentplane-py[service]'"
    ) from exc

from agentplane.service.schemas import AuditEntry

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditEntry])
async def read_audit(
    request: Request,
    n: int = Query(default=100, ge=1, le=10000, description="Number of recent lines to return"),
    agent_id: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
) -> list[AuditEntry]:
    audit = request.app.state.audit
    if audit is None:
        raise HTTPException(status_code=503, detail="Audit trail not available")

    path = audit.path
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read audit log: {exc}")

    # Take last N lines
    lines = lines[-n:] if len(lines) > n else lines

    entries: list[AuditEntry] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Filter by agent_id / tenant_id if provided
        if agent_id is not None and data.get("agent_id") != agent_id:
            continue
        if tenant_id is not None and data.get("tenant_id") != tenant_id:
            continue

        try:
            entry = AuditEntry.model_validate(data)
            entries.append(entry)
        except Exception:
            continue

    return entries
