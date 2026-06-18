from __future__ import annotations

"""Entry point: python -m agentplane.service"""

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "agentplane service requires uvicorn — install with: pip install 'agentplane-py[service]'"
    ) from exc

from agentplane.service.app import create_app  # noqa: E402

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
