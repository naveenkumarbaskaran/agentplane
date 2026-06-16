import pytest

from agentplane import AllowlistRule, InMemoryPolicyStore, Selector
from agentplane.core.exceptions import PolicyNotFound
from agentplane.core.policy import Policy, PolicyStatus


def make_policy(id="test.p1", status=PolicyStatus.ACTIVE):
    return Policy(id=id, selector=Selector.all(), blocking=[AllowlistRule(tools=["search"])], status=status)


def test_store_save_and_get():
    store = InMemoryPolicyStore()
    store.save(make_policy())
    p = store.get("test.p1")
    assert p.id == "test.p1"


def test_store_get_missing_raises():
    store = InMemoryPolicyStore()
    with pytest.raises(PolicyNotFound):
        store.get("nonexistent")


def test_store_delete():
    store = InMemoryPolicyStore()
    store.save(make_policy())
    store.delete("test.p1")
    with pytest.raises(PolicyNotFound):
        store.get("test.p1")


def test_store_list_active():
    store = InMemoryPolicyStore()
    store.save(make_policy("p1", PolicyStatus.ACTIVE))
    store.save(make_policy("p2", PolicyStatus.RETIRED))
    active = store.list_active()
    assert len(active) == 1
    assert active[0].id == "p1"


def test_store_count():
    store = InMemoryPolicyStore()
    store.save(make_policy("p1"))
    store.save(make_policy("p2"))
    assert store.count() == 2
