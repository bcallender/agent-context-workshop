"""The adoption lever: one agent with BOTH graph + filesystem tools, where the system
prompt is the only variable. naive vs nudged (vs nudged_v2) → adoption-rate before/after.

Plus tool-call accounting: `tool_breakdown` counts which tools a run called, and `adoption`
turns that into the graph-tool share of code lookups — the metric that gates every capability win.
"""

from __future__ import annotations

from dataclasses import dataclass

GRAPH_TOOLS = {
    "search",
    "get_symbol",
    "blast_radius",
    "implementors",
    "methods_of",
    "public_api",
    "neighborhood",
}


@dataclass
class FsDeps:
    backend: object


NAIVE_PROMPT = (
    "You answer questions about a Rust codebase. You have filesystem tools (grep, glob, "
    "read_file, ls) over the source tree, and graph tools (search, get_symbol, blast_radius, "
    "implementors, methods_of, public_api, neighborhood) over a precomputed code graph. "
    "Find the answer and cite each definition by its source file and line (e.g. posting_list.rs:27)."
)
NUDGED_PROMPT = (
    "You answer questions about a Rust codebase using a precomputed code graph. PREFER the graph "
    "tools — they resolve symbols across crates with no false positives. Resolve any bare name with "
    "`search` FIRST to get its canonical qualified_name, then use blast_radius / implementors / "
    "methods_of. Only fall back to grep/glob/read_file if the graph genuinely has no answer. Ground "
    "every claim in tool output and cite file:line. If a tool returns nothing, say so — never invent."
)
# v2: same lever (prompt only), but harder — a question-type->tool decision rule, a worked example, and
# the collision-as-cost framing. Tests the ceiling of the nudge before reaching for tool-design changes.
NUDGED_V2_PROMPT = (
    "You answer questions about a Rust codebase. A precomputed code graph — built from the compiler's "
    "own name resolution, zero false positives — is your primary tool. "
    "DECISION RULE: any question about relationships or structure (what implements / returns / takes / "
    "calls X, or which of several same-named types is meant) is a GRAPH question. grep cannot answer it "
    "safely — look-alike names like PostingList, PostingListView, and CompressedPostingList collide and "
    "produce confident false matches. Resolve a bare name with `search` FIRST to get its qualified_name, "
    "then blast_radius / implementors / methods_of / public_api. "
    "Example — 'what implements EncodedVectors?' -> search('EncodedVectors'), then implementors(qualified_name). "
    "Reach for grep / glob / read_file ONLY to find free text in comments or string literals the graph "
    "doesn't index. Cite every definition by file:line; if a tool returns nothing, say so — never invent."
)


def _register_graph_tools(agent, graph_tools):
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


def build_fallback_agent(model, graph_tools, fs_toolset, *, nudge, prompt=None):
    """Agent C: BOTH graph + filesystem tools. The system prompt is the only lever —
    a clean single-variable before/after on adoption. `prompt=` overrides for ablations (e.g. v2 nudge)."""
    from pydantic_ai import Agent
    from pydantic_ai.settings import ModelSettings

    system_prompt = prompt if prompt is not None else (NUDGED_PROMPT if nudge else NAIVE_PROMPT)
    agent = Agent(
        model,
        toolsets=[fs_toolset],
        deps_type=FsDeps,
        retries=3,
        model_settings=ModelSettings(temperature=0),
        system_prompt=system_prompt,
    )
    _register_graph_tools(agent, graph_tools)
    return agent


def tool_breakdown(res):
    """Count tool calls by name from the run's message history."""
    from pydantic_ai.messages import ToolCallPart

    counts = {}
    if res is None:
        return counts
    for message in res.all_messages():
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolCallPart):
                counts[part.tool_name] = counts.get(part.tool_name, 0) + 1
    return counts


def adoption(counts):
    """graph-tool calls / (graph + fallback). None if no code-lookup tools were called."""
    graph_calls = sum(n for t, n in counts.items() if t in GRAPH_TOOLS)
    other_calls = sum(n for t, n in counts.items() if t not in GRAPH_TOOLS)
    total = graph_calls + other_calls
    return (round(graph_calls / total, 2) if total else None), graph_calls, other_calls
