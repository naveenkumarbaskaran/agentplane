from __future__ import annotations

from agentplane.core.exceptions import PolicyNotFound
from agentplane.core.policy import Policy


class InMemoryPolicyStore:
    """Thread-safe in-process policy store. Default for embedded use."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    def save(self, policy: Policy) -> None:
        self._policies[policy.id] = policy

    def get(self, policy_id: str) -> Policy:
        p = self._policies.get(policy_id)
        if p is None:
            raise PolicyNotFound(policy_id)
        return p

    def delete(self, policy_id: str) -> None:
        if policy_id not in self._policies:
            raise PolicyNotFound(policy_id)
        del self._policies[policy_id]

    def list_active(self) -> list[Policy]:
        return [p for p in self._policies.values() if p.is_active()]

    def list_all(self) -> list[Policy]:
        return list(self._policies.values())

    def count(self) -> int:
        return len(self._policies)
