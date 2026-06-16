from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class DegradationMode(StrEnum):
    READ_ONLY = "read_only"
    NO_EXTERNAL = "no_external"
    RATE_THROTTLE = "rate_throttle"
    HUMAN_LOOP = "human_loop"
    SAFE_TOOLS_ONLY = "safe_tools_only"
    FULL_BLOCK = "full_block"


@dataclass
class DegradationConfig:
    """Describes how an agent should behave in degraded state and how to recover.

    Usage::

        cfg = DegradationConfig(
            mode=DegradationMode.READ_ONLY,
            recover_after="30m",
            recover_when=None,
            recover_on="auto",
        )
    """

    mode: DegradationMode
    recover_after: str | None = "30m"
    recover_when: str | None = None
    recover_on: str = "auto"
    reason: str = ""
    entered_at: float = field(default_factory=time.time)

    def recover_after_seconds(self) -> float | None:
        if not self.recover_after:
            return None
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        t = self.recover_after
        if t[-1] in units:
            return float(t[:-1]) * units[t[-1]]
        return float(t)

    def is_expired(self) -> bool:
        secs = self.recover_after_seconds()
        if secs is None:
            return False
        return (time.time() - self.entered_at) >= secs


class DegradationTracker:
    """Tracks per-agent degradation state with automatic recovery."""

    def __init__(self) -> None:
        self._states: dict[str, DegradationConfig] = {}

    def degrade(self, agent_id: str, config: DegradationConfig) -> None:
        self._states[agent_id] = config

    def recover(self, agent_id: str) -> None:
        self._states.pop(agent_id, None)

    def is_degraded(self, agent_id: str) -> bool:
        cfg = self._states.get(agent_id)
        if cfg is None:
            return False
        if cfg.is_expired():
            self.recover(agent_id)
            return False
        return True

    def get_mode(self, agent_id: str) -> DegradationMode | None:
        if not self.is_degraded(agent_id):
            return None
        return self._states[agent_id].mode

    def get_config(self, agent_id: str) -> DegradationConfig | None:
        if not self.is_degraded(agent_id):
            return None
        return self._states[agent_id]

    def all_degraded(self) -> dict[str, DegradationConfig]:
        self._gc()
        return dict(self._states)

    def _gc(self) -> None:
        expired = [aid for aid, cfg in self._states.items() if cfg.is_expired()]
        for aid in expired:
            self.recover(aid)
