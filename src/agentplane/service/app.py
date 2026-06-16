from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "agentplane service requires fastapi — install with: pip install 'agentplane-py[service]'"
    ) from exc

from agentplane import __version__
from agentplane.service.routes import agents as agents_router
from agentplane.service.routes import audit as audit_router
from agentplane.service.routes import policies as policies_router
from agentplane.service.schemas import HealthResponse


def create_app(
    engine: Any = None,
    plug_board: Any = None,
    version_manager: Any = None,
    audit: Any = None,
) -> FastAPI:
    """Create and return the agentplane FastAPI application.

    Parameters
    ----------
    engine:
        PolicyEngine instance. If None, policy routes return 503.
    plug_board:
        PlugBoard instance. If None, agent plug/unplug routes return 503.
    version_manager:
        VersionManager instance. If None, versioning routes return 503.
    audit:
        AuditTrail instance. If None, audit routes return 503.
    """
    app = FastAPI(
        title="agentplane",
        description="Runtime policy control plane for production AI agents.",
        version=__version__,
    )

    # Store shared objects on app.state
    app.state.engine = engine
    app.state.plug_board = plug_board
    app.state.version_manager = version_manager
    app.state.audit = audit

    # Include routers
    app.include_router(policies_router.router)
    app.include_router(agents_router.router)
    app.include_router(audit_router.router)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    return app
