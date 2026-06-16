from agentplane import PolicyContext, Selector


def make_ctx(**kwargs):
    defaults = dict(agent_id="agent-1", tenant_id="acme", hookpoint="before_tool_call", tool_name="search")
    return PolicyContext.new(**{**defaults, **kwargs})


def test_selector_all_matches():
    s = Selector.all()
    assert s.matches(make_ctx())


def test_selector_agent_match():
    s = Selector(agents=["agent-1"])
    assert s.matches(make_ctx(agent_id="agent-1"))
    assert not s.matches(make_ctx(agent_id="agent-2"))


def test_selector_wildcard_agent():
    s = Selector(agents=["*"])
    assert s.matches(make_ctx(agent_id="anything"))


def test_selector_tenant_match():
    s = Selector(tenants=["acme"])
    assert s.matches(make_ctx(tenant_id="acme"))
    assert not s.matches(make_ctx(tenant_id="siemens"))


def test_selector_tool_match():
    s = Selector(tools=["sql_run"])
    assert s.matches(make_ctx(tool_name="sql_run"))
    assert not s.matches(make_ctx(tool_name="delete_db"))


def test_selector_hookpoint_match():
    s = Selector(hookpoints=["before_tool_call"])
    assert s.matches(make_ctx(hookpoint="before_tool_call"))
    assert not s.matches(make_ctx(hookpoint="after_tool_call"))


def test_selector_tags_match():
    s = Selector(tags={"env": "prod"})
    assert s.matches(make_ctx(tags={"env": "prod"}))
    assert not s.matches(make_ctx(tags={"env": "dev"}))
    assert not s.matches(make_ctx())


def test_selector_multi_condition():
    s = Selector(tenants=["acme"], tools=["sql_run"])
    assert s.matches(make_ctx(tenant_id="acme", tool_name="sql_run"))
    assert not s.matches(make_ctx(tenant_id="acme", tool_name="delete_db"))
    assert not s.matches(make_ctx(tenant_id="siemens", tool_name="sql_run"))
