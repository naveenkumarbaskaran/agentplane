from __future__ import annotations


class AgentplaneError(Exception):
    """Base exception for all agentplane errors."""


class PolicyBlocked(AgentplaneError):
    """Raised when a blocking policy denies execution."""

    def __init__(self, policy_id: str, rule: str, reason: str) -> None:
        self.policy_id = policy_id
        self.rule = rule
        self.reason = reason
        super().__init__(f"[{policy_id}:{rule}] {reason}")


class PolicyDegraded(AgentplaneError):
    """Raised when an agent has been put into a degradation mode."""

    def __init__(self, policy_id: str, mode: str, reason: str) -> None:
        self.policy_id = policy_id
        self.mode = mode
        self.reason = reason
        super().__init__(f"[{policy_id}] degraded to {mode}: {reason}")


class PolicyConflict(AgentplaneError):
    """Raised when two policies produce irreconcilable conflicting decisions."""

    def __init__(self, policy_a: str, policy_b: str, detail: str) -> None:
        self.policy_a = policy_a
        self.policy_b = policy_b
        super().__init__(f"Policy conflict between {policy_a} and {policy_b}: {detail}")


class PolicyNotFound(AgentplaneError):
    def __init__(self, policy_id: str) -> None:
        self.policy_id = policy_id
        super().__init__(f"Policy not found: {policy_id}")


class PolicyVersionError(AgentplaneError):
    def __init__(self, policy_id: str, version: int, detail: str = "") -> None:
        self.policy_id = policy_id
        self.version = version
        super().__init__(f"Version error for {policy_id} v{version}: {detail}")


class EscalationError(AgentplaneError):
    def __init__(self, policy_id: str, level: int, detail: str = "") -> None:
        self.policy_id = policy_id
        self.level = level
        super().__init__(f"Escalation error [{policy_id}] level {level}: {detail}")


class SyncError(AgentplaneError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Sync error: {detail}")
