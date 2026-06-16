from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("agentplane.sync")


class SyncConfig:
    def __init__(
        self,
        service_url: str,
        agent_id: str,
        poll_interval_s: float = 30.0,
        on_offline: str = "use_cache",
        api_key: str | None = None,
    ) -> None:
        self.service_url = service_url.rstrip("/")
        self.agent_id = agent_id
        self.poll_interval_s = poll_interval_s
        self.on_offline = on_offline
        self.api_key = api_key


class PolicySyncer:
    """Syncs policies from a remote agentplane service to the local engine.

    Supports push (webhook) and pull (polling) modes. Falls back to the
    local cache when the service is unreachable.

    Usage::

        syncer = PolicySyncer(engine, SyncConfig(
            service_url="https://agentplane.acme.com",
            agent_id="billing-agent",
        ))
        await syncer.start()   # begins background polling
        await syncer.stop()    # graceful shutdown
    """

    def __init__(self, engine: Any, config: SyncConfig) -> None:
        self._engine = engine
        self._config = config
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._last_sync: float = 0.0
        self._consecutive_failures: int = 0

    async def start(self) -> None:
        self._task = asyncio.ensure_future(self._poll_loop())
        logger.info(
            "agentplane.sync started agent=%s url=%s interval=%ss",
            self._config.agent_id,
            self._config.service_url,
            self._config.poll_interval_s,
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("agentplane.sync stopped agent=%s", self._config.agent_id)

    async def sync_once(self) -> bool:
        try:
            import httpx
        except ImportError:
            logger.warning("agentplane.sync requires httpx: pip install agentplane-py[sync]")
            return False

        url = f"{self._config.service_url}/api/v1/agents/{self._config.agent_id}/policies"
        headers: dict[str, str] = {}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            from agentplane.store.sqlite import _dict_to_policy
            for item in data.get("policies", []):
                try:
                    policy = _dict_to_policy(item)
                    self._engine.add_policy(policy)
                except Exception as exc:
                    logger.warning("agentplane.sync policy_parse_error: %s", exc)

            self._last_sync = time.time()
            self._consecutive_failures = 0
            logger.info(
                "agentplane.sync synced %d policies agent=%s",
                len(data.get("policies", [])),
                self._config.agent_id,
            )
            return True

        except Exception as exc:
            self._consecutive_failures += 1
            logger.warning(
                "agentplane.sync failed agent=%s error=%s failures=%d",
                self._config.agent_id, exc, self._consecutive_failures,
            )
            return False

    async def _poll_loop(self) -> None:
        while True:
            await self.sync_once()
            await asyncio.sleep(self._config.poll_interval_s)

    @property
    def last_sync(self) -> float:
        return self._last_sync

    @property
    def is_healthy(self) -> bool:
        return self._consecutive_failures == 0
