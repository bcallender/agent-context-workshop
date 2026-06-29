"""Wire the curated graph tools (and participant-authored Cypher tools) onto a
Pydantic AI agent. The cypher_tool helper is the workshop's build-your-own-tool
primitive: hand it a Cypher string, get back an agent-callable function."""

from __future__ import annotations

from collections.abc import Callable

from context_workshop.graph.tools import GraphTools


def cypher_tool(
    graph_tools: GraphTools,
    cypher: str,
    *,
    shape: Callable[[list[dict]], list[dict]] = lambda rows: rows,
) -> Callable[..., list[dict]]:
    """Turn a Cypher query into a callable tool.

    Participants write a Cypher string; this returns a plain function that
    executes it against the graph. Keyword arguments become Cypher parameters.
    The optional *shape* function post-processes rows before returning.
    """

    def _tool(**params) -> list[dict]:
        with graph_tools._driver.session() as s:
            return shape(s.run(cypher, **params).data())

    return _tool


def build_graph_agent(
    model: str,
    graph_tools: GraphTools,
    extra_tools: list | None = None,
):
    """Return a Pydantic AI Agent with the curated GraphTools methods registered.

    The seven curated tools (search, get_symbol, blast_radius, implementors,
    methods_of, public_api, neighborhood) are registered as plain tools (no
    RunContext). Pass *extra_tools* to add participant-authored cypher_tool
    callables or any other plain functions.
    """
    from pydantic_ai import Agent
    from pydantic_ai.settings import ModelSettings

    agent = Agent(
        model,
        retries=3,  # match the grep/fallback agents (was default 1)
        model_settings=ModelSettings(
            temperature=0
        ),  # symmetry with B/C; no-op for reasoning models
        system_prompt=(
            "You answer questions about a Rust codebase using graph traversal tools. "
            "Symbols are identified by their full canonical qualified_name "
            "(e.g. `crate::module::Type`), never a bare name: if you only have a bare "
            "name, call `search` FIRST to resolve it to its qualified_name, then pass "
            "that exact string to the other tools. For 'what breaks if I change X' use "
            "blast_radius. Ground every claim in tool output: each symbol, file, and "
            "line in your answer must come verbatim from a tool result. If a tool "
            "returns no results, say so plainly — never invent symbols, files, or lines."
        ),
    )
    for fn in (
        graph_tools.search,
        graph_tools.get_symbol,
        graph_tools.blast_radius,
        graph_tools.implementors,
        graph_tools.methods_of,
        graph_tools.public_api,
        graph_tools.neighborhood,
    ):
        agent.tool_plain(fn)
    for fn in extra_tools or []:
        agent.tool_plain(fn)
    return agent
