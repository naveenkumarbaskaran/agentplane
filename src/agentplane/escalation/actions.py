from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Block:
    """Immediately block agent execution."""
    reason: str = "policy block"


@dataclass
class Degrade:
    """Put agent into a degraded mode."""
    mode: str = "read_only"
    recover_after: str = "30m"
    reason: str = "policy degradation"


@dataclass
class Alert:
    """Send an alert without stopping the agent."""
    channel: str = "log"
    webhook_url: str | None = None
    message: str = ""


@dataclass
class HITL:
    """Route to human-in-the-loop. Blocks until approved or timeout."""
    timeout: str = "5m"
    fallback: str = "block"
    message: str = ""

    def timeout_seconds(self) -> float:
        units = {"s": 1, "m": 60, "h": 3600}
        t = self.timeout
        if t[-1] in units:
            return float(t[:-1]) * units[t[-1]]
        return float(t)


EscalationAction = Block | Degrade | Alert | HITL
