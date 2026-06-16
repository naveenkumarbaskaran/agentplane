from __future__ import annotations

try:
    from agentplane.service.app import create_app

    __all__ = ["create_app"]
except ImportError:
    __all__ = []
