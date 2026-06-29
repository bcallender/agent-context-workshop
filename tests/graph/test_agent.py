"""Tests for graph agent wiring and cypher_tool helper."""

from context_workshop.graph.agent import build_graph_agent, cypher_tool


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, cypher, **params):
        class R:
            def data(self_inner):
                return [{"qualified_name": params.get("qn", "x")}]

        return R()


class _FakeDriver:
    def session(self):
        return _FakeSession()


class _FakeTools:
    def __init__(self):
        self._driver = _FakeDriver()


def test_cypher_tool_runs_participant_cypher():
    tool = cypher_tool(_FakeTools(), "MATCH (n) WHERE n.qualified_name=$qn RETURN n")
    assert tool(qn="c::A") == [{"qualified_name": "c::A"}]


def test_build_graph_agent_registers_tools():
    from context_workshop.graph.tools import GraphTools

    agent = build_graph_agent("test", GraphTools(_FakeDriver()))
    names = {t.name for t in agent._function_toolset.tools.values()}
    all_seven = {
        "search",
        "get_symbol",
        "blast_radius",
        "implementors",
        "methods_of",
        "public_api",
        "neighborhood",
    }
    assert all_seven <= names
