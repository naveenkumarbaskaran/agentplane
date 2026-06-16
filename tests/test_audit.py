import tempfile

import pytest

from agentplane import PolicyContext
from agentplane.audit.trail import AuditTrail, get_default_audit, set_default_audit


def ctx():
    return PolicyContext.new(agent_id="a1", tenant_id="acme")


@pytest.mark.asyncio
async def test_audit_writes_entries():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    audit = AuditTrail(path=path)
    for i in range(5):
        await audit.record(
            policy_id=f"p{i}", rule="test", ctx=ctx(),
            status="allow", reason="ok", duration_ms=1.0,
        )
    import pathlib
    lines = pathlib.Path(path).read_text().strip().split("\n")
    assert len(lines) == 5
    pathlib.Path(path).unlink()


@pytest.mark.asyncio
async def test_audit_entry_fields():
    import json
    import pathlib
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    audit = AuditTrail(path=path)
    await audit.record(
        policy_id="test.p1", rule="rate_limit", ctx=ctx(),
        status="block", reason="exceeded", duration_ms=5.2,
    )
    entry = json.loads(pathlib.Path(path).read_text().strip())
    assert entry["policy.id"] == "test.p1"
    assert entry["policy.rule"] == "rate_limit"
    assert entry["policy.status"] == "block"
    assert entry["agent_id"] == "a1"
    pathlib.Path(path).unlink()


@pytest.mark.asyncio
async def test_default_audit_singleton():
    audit1 = get_default_audit()
    audit2 = get_default_audit()
    assert audit1 is audit2


@pytest.mark.asyncio
async def test_set_default_audit():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    new_audit = AuditTrail(path=path)
    set_default_audit(new_audit)
    assert get_default_audit() is new_audit
    import pathlib
    pathlib.Path(path).unlink(missing_ok=True)
