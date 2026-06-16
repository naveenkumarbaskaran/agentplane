from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentplane.core.exceptions import PolicyNotFound
from agentplane.core.policy import Policy, PolicyStatus


class SqlitePolicyStore:
    """Persistent SQLite-backed policy store for embedded + service use.

    Policies are serialised as JSON. Rules are stored by class name and
    reconstructed via the rule registry on load.

    Requires: aiosqlite (optional dep)

    Usage::

        store = SqlitePolicyStore("~/.agentplane/policies.db")
        await store.init()
        await store.save(policy)
        policies = await store.list_active()
    """

    def __init__(self, path: str = "~/.agentplane/policies.db") -> None:
        import os
        self._path = os.path.expanduser(path)
        self._db: Any = None

    async def init(self) -> None:
        try:
            import aiosqlite as _aiosqlite
        except ImportError as exc:
            raise ImportError(
                "SqlitePolicyStore requires aiosqlite: pip install agentplane-py[sqlite]"
            ) from exc
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await _aiosqlite.connect(self._path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                data JSON NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        await self._db.commit()

    async def save(self, policy: Policy) -> None:
        data = _policy_to_dict(policy)
        await self._db.execute("""
            INSERT OR REPLACE INTO policies (id, version, status, priority, data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (policy.id, policy.version, policy.status.value,
              policy.priority, json.dumps(data), time.time()))
        await self._db.commit()

    async def get(self, policy_id: str) -> Policy:
        async with self._db.execute(
            "SELECT data FROM policies WHERE id = ?", (policy_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise PolicyNotFound(policy_id)
        return _dict_to_policy(json.loads(row[0]))

    async def delete(self, policy_id: str) -> None:
        await self._db.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
        await self._db.commit()

    async def list_active(self) -> list[Policy]:
        async with self._db.execute(
            "SELECT data FROM policies WHERE status = ?", (PolicyStatus.ACTIVE.value,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [_dict_to_policy(json.loads(r[0])) for r in rows]

    async def list_all(self) -> list[Policy]:
        async with self._db.execute("SELECT data FROM policies") as cursor:
            rows = await cursor.fetchall()
        return [_dict_to_policy(json.loads(r[0])) for r in rows]

    async def close(self) -> None:
        if self._db:
            await self._db.close()


def _policy_to_dict(policy: Policy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "version": policy.version,
        "status": policy.status.value,
        "priority": policy.priority,
        "description": policy.description,
        "tags": policy.tags,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
        "blocking": [{"type": type(r).__name__, "priority": r.priority} for r in policy.blocking],
        "non_blocking": [{"type": type(r).__name__} for r in policy.non_blocking],
        "metadata": policy.metadata,
    }


def _dict_to_policy(d: dict[str, Any]) -> Policy:
    from agentplane.core.policy import Policy, PolicyStatus
    return Policy(
        id=d["id"],
        version=d["version"],
        status=PolicyStatus(d["status"]),
        priority=d["priority"],
        description=d.get("description", ""),
        tags=d.get("tags", {}),
        created_at=d.get("created_at", time.time()),
        updated_at=d.get("updated_at", time.time()),
        metadata=d.get("metadata", {}),
    )
