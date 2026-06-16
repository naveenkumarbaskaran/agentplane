import pytest

from agentplane import AllowlistRule, Selector, VersionManager
from agentplane.core.exceptions import PolicyVersionError
from agentplane.core.policy import Policy


def base_policy(version=1):
    return Policy(
        id="test.versioned",
        selector=Selector(tenants=["acme"]),
        blocking=[AllowlistRule(tools=["search"])],
        version=version,
    )


def test_publish_and_history():
    vm = VersionManager()
    vm.publish(base_policy(1), changelog="Initial")
    vm.publish(base_policy(2), changelog="v2")
    history = vm.history("test.versioned")
    assert len(history) == 2
    assert history[0].version == 1
    assert history[1].version == 2


def test_publish_duplicate_version_raises():
    vm = VersionManager()
    vm.publish(base_policy(1))
    with pytest.raises(PolicyVersionError):
        vm.publish(base_policy(1))


def test_diff():
    from agentplane import RedactRule
    vm = VersionManager()
    p1 = Policy(
        id="test.diff", version=1,
        blocking=[AllowlistRule(tools=["search"])],
    )
    p2 = Policy(
        id="test.diff", version=2,
        blocking=[AllowlistRule(tools=["search"]), RedactRule(fields=["ssn"])],
    )
    vm.publish(p1)
    vm.publish(p2)
    diff = vm.diff("test.diff", 1, 2)
    assert "RedactRule" in diff.added_blocking
    assert diff.removed_blocking == []


def test_rollback():
    vm = VersionManager()
    vm.publish(base_policy(1), changelog="v1")
    vm.publish(base_policy(2), changelog="v2")
    restored = vm.rollback("test.versioned", to_version=1)
    assert restored.version == 3
    history = vm.history("test.versioned")
    assert len(history) == 3


def test_rollback_missing_version_raises():
    vm = VersionManager()
    vm.publish(base_policy(1))
    with pytest.raises(PolicyVersionError):
        vm.rollback("test.versioned", to_version=99)


def test_latest():
    vm = VersionManager()
    vm.publish(base_policy(1))
    vm.publish(base_policy(2))
    latest = vm.latest("test.versioned")
    assert latest is not None
    assert latest.version == 2
