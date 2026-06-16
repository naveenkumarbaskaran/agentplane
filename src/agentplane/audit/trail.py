from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from agentplane.core.context import PolicyContext

logger = logging.getLogger("agentplane.audit")

AUDIT_STATUS = frozenset({"allow", "block", "degrade", "escalate", "skip", "error"})


class AuditTrail:
    """Append-only JSONL audit log for every policy evaluation.

    Every evaluation — allow, block, degrade, escalate — is recorded.
    This cannot be disabled: it is a security invariant.

    Usage::

        audit = AuditTrail()                           # ~/.agentplane/audit.jsonl
        audit = AuditTrail(path="/var/log/policies.jsonl")
        await audit.record(policy_id="acme.v1", rule="rate_limit",
                           ctx=ctx, status="block", reason="exceeded")
    """

    def __init__(self, path: str | None = None) -> None:
        import os
        self._path = Path(path or os.path.expanduser("~/.agentplane/audit.jsonl"))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    async def record(
        self,
        *,
        policy_id: str,
        rule: str,
        ctx: PolicyContext,
        status: str,
        reason: str = "",
        duration_ms: float = 0.0,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if status not in AUDIT_STATUS:
            status = "error"

        entry: dict[str, Any] = {
            "ts": time.time(),
            "policy.id": policy_id,
            "policy.rule": rule,
            "policy.status": status,
            "policy.reason": reason,
            "policy.duration_ms": round(duration_ms, 2),
            "agent_id": ctx.agent_id,
            "tenant_id": ctx.tenant_id,
            "session_id": ctx.session_id,
            "trace_id": ctx.trace_id,
            "hookpoint": ctx.hookpoint,
            "tool_name": ctx.tool_name,
        }
        if extra:
            entry.update(extra)

        line = json.dumps(entry, default=str)
        try:
            async with self._lock:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._write_line, line
                )
        except OSError as exc:
            import sys
            print(f"[agentplane.audit] WARNING: could not write: {exc}", file=sys.stderr)

    def _write_line(self, line: str) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


_default_audit: AuditTrail | None = None


def get_default_audit() -> AuditTrail:
    global _default_audit
    if _default_audit is None:
        _default_audit = AuditTrail()
    return _default_audit


def set_default_audit(audit: AuditTrail) -> None:
    global _default_audit
    _default_audit = audit
