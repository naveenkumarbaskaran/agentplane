from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

from agentplane.core.exceptions import PolicyNotFound, PolicyVersionError
from agentplane.core.policy import Policy, PolicyStatus


@dataclass
class PolicyVersion:
    policy_id: str
    version: int
    policy: Policy
    created_at: float = field(default_factory=time.time)
    changelog: str = ""


@dataclass
class PolicyDiff:
    policy_id: str
    from_version: int
    to_version: int
    added_blocking: list[str] = field(default_factory=list)
    removed_blocking: list[str] = field(default_factory=list)
    added_non_blocking: list[str] = field(default_factory=list)
    removed_non_blocking: list[str] = field(default_factory=list)
    priority_changed: bool = False
    selector_changed: bool = False
    status_changed: bool = False


class VersionManager:
    """Manages versioned policy history with diff and rollback.

    Every publish creates a new version. Rollback restores any prior version
    as a new active version (preserving the audit trail — no history is lost).

    Usage::

        vm = VersionManager()
        v1 = vm.publish(policy)
        policy_v2 = policy.bump_version()
        v2 = vm.publish(policy_v2)
        diff = vm.diff(policy.id, 1, 2)
        active = vm.rollback(policy.id, to_version=1)
    """

    def __init__(self) -> None:
        self._history: dict[str, list[PolicyVersion]] = {}

    def publish(self, policy: Policy, changelog: str = "") -> PolicyVersion:
        pv = PolicyVersion(
            policy_id=policy.id,
            version=policy.version,
            policy=copy.deepcopy(policy),
            changelog=changelog,
        )
        self._history.setdefault(policy.id, [])
        existing = [v for v in self._history[policy.id] if v.version == policy.version]
        if existing:
            raise PolicyVersionError(policy.id, policy.version, "version already exists")
        self._history[policy.id].append(pv)
        return pv

    def rollback(self, policy_id: str, to_version: int) -> Policy:
        versions = self._history.get(policy_id, [])
        match = next((v for v in versions if v.version == to_version), None)
        if not match:
            raise PolicyVersionError(policy_id, to_version, "version not found")
        new_version = max(v.version for v in versions) + 1
        restored = copy.deepcopy(match.policy)
        from dataclasses import replace
        restored = replace(
            restored,
            version=new_version,
            status=PolicyStatus.ACTIVE,
            updated_at=time.time(),
        )
        self.publish(restored, changelog=f"rollback from v{to_version}")
        return restored

    def diff(self, policy_id: str, from_version: int, to_version: int) -> PolicyDiff:
        def _get(v: int) -> Policy:
            versions = self._history.get(policy_id, [])
            match = next((pv for pv in versions if pv.version == v), None)
            if not match:
                raise PolicyVersionError(policy_id, v, "version not found")
            return match.policy

        p_from = _get(from_version)
        p_to = _get(to_version)

        from_blocking = {type(r).__name__ for r in p_from.blocking}
        to_blocking = {type(r).__name__ for r in p_to.blocking}
        from_nb = {type(r).__name__ for r in p_from.non_blocking}
        to_nb = {type(r).__name__ for r in p_to.non_blocking}

        return PolicyDiff(
            policy_id=policy_id,
            from_version=from_version,
            to_version=to_version,
            added_blocking=sorted(to_blocking - from_blocking),
            removed_blocking=sorted(from_blocking - to_blocking),
            added_non_blocking=sorted(to_nb - from_nb),
            removed_non_blocking=sorted(from_nb - to_nb),
            priority_changed=p_from.priority != p_to.priority,
            selector_changed=p_from.selector != p_to.selector,
            status_changed=p_from.status != p_to.status,
        )

    def history(self, policy_id: str) -> list[PolicyVersion]:
        return list(self._history.get(policy_id, []))

    def latest(self, policy_id: str) -> PolicyVersion | None:
        versions = self._history.get(policy_id, [])
        if not versions:
            return None
        return max(versions, key=lambda v: v.version)

    def promote(self, policy_id: str, from_env: str, to_env: str) -> Policy:
        latest = self.latest(policy_id)
        if not latest:
            raise PolicyNotFound(policy_id)
        from dataclasses import replace
        promoted = replace(
            latest.policy,
            id=f"{to_env}.{policy_id}",
            version=1,
            tags={**latest.policy.tags, "env": to_env, "promoted_from": from_env},
            created_at=time.time(),
            updated_at=time.time(),
        )
        return promoted
