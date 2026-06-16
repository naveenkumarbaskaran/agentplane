from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RuleVerdict(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    DEGRADE = "degrade"
    ESCALATE = "escalate"
    SKIP = "skip"


@dataclass
class RuleResult:
    verdict: RuleVerdict
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, reason: str = "") -> RuleResult:
        return cls(verdict=RuleVerdict.ALLOW, reason=reason)

    @classmethod
    def block(cls, reason: str) -> RuleResult:
        return cls(verdict=RuleVerdict.BLOCK, reason=reason)

    @classmethod
    def degrade(cls, mode: str, reason: str) -> RuleResult:
        return cls(verdict=RuleVerdict.DEGRADE, reason=reason, metadata={"mode": mode})

    @classmethod
    def escalate(cls, level: int, reason: str) -> RuleResult:
        return cls(verdict=RuleVerdict.ESCALATE, reason=reason, metadata={"level": level})

    @classmethod
    def skip(cls) -> RuleResult:
        return cls(verdict=RuleVerdict.SKIP)


class BlockingRule(ABC):
    """Evaluated synchronously. Agent waits for the decision.
    Must return a RuleResult. Raising PolicyBlocked is also valid.
    """

    priority: int = 100
    name: str = ""

    @abstractmethod
    async def evaluate(self, ctx: Any) -> RuleResult:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(priority={self.priority})"


class NonBlockingRule(ABC):
    """Evaluated asynchronously. Agent never waits.
    Failures are logged but never propagate to the agent.
    """

    name: str = ""

    @abstractmethod
    async def evaluate(self, ctx: Any) -> None:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
