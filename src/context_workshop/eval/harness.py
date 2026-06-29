"""The graph-vs-grep eval run.

Three measurements:
  1. CAPABILITY/EFFICIENCY — Agent A (graph-only) vs Agent B (grep-only), per class.
  2. ADOPTION — Agent C has BOTH graph + filesystem tools; we count which it calls.
     naive prompt vs nudged prompt → adoption-rate before/after.
  3. CONSISTENCY (with repeat>1) — pass@k (ever right) vs pass^k (right EVERY run): the determinism win.

Generate the committed cache:
  uv run python -m context_workshop.eval.harness --all --out data/eval/graph_vs_grep_cache.json
Nudge ablation (naive vs nudged vs nudged_v2), separate output:
  uv run python -m context_workshop.eval.harness --nudge-ablation --out data/eval/nudge_experiment.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from context_workshop.eval.corpus import GOLD
from context_workshop.eval.nudges import (
    NUDGED_V2_PROMPT,
    FsDeps,
    adoption,
    build_fallback_agent,
    tool_breakdown,
)
from context_workshop.eval.scorer import cites_all, scorer_selftest, set_recall

ROOT = Path.cwd()

# Quiet the neo4j driver's server-notification spam (blast_radius's edge-type union includes the
# deferred CALLS layer, which emits an "unknown relationship type" notification until loaded).
for _n in ("neo4j", "neo4j.notifications", "neo4j.pool", "neo4j.io"):
    logging.getLogger(_n).setLevel(logging.ERROR)

DOC = ROOT / "data/cache/cargo-target/doc"
CRATES = ["posting_list", "sparse", "segment", "quantization", "gridstore"]
FS_ROOT = ROOT / "data/cache/eval_tree"
ADOPT_CLASSES = (
    "typedep",
    "collision",
    "control",
)  # private isn't in the public graph → no adoption

# ---- env / keys ----
load_dotenv(ROOT / ".env")  # no-op if absent; won't override already-exported vars
HAS_KEY = bool(os.getenv("OPENROUTER_API_KEY"))
# One key: OPENROUTER_API_KEY → any model. The committed cache (data/eval/) was generated with
# openrouter:openai/gpt-5.4-mini at k=5. Pick any model with AGENT_MODEL
# (e.g. "openrouter:anthropic/claude-sonnet-4", "openrouter:openai/gpt-5-mini").
AGENT_MODEL = os.getenv("AGENT_MODEL", "openrouter:openai/gpt-5.4-mini")


def _maybe_logfire():
    """Opt-in eval tracing — a no-op unless `logfire` is installed AND a LOGFIRE_TOKEN (or EVAL_LOGFIRE=1)
    is set, so the default `uv sync` stays slim and offline. With a token, every model request and tool
    call streams to the Logfire UI, where one trace *shows* the adoption metric: the agent reaching for
    the graph vs falling back to grep. Enable with `uv sync --extra trace`, then
    `EVAL_LOGFIRE=1 LOGFIRE_TOKEN=... uv run python -m context_workshop.eval.harness ...`."""
    if not (os.getenv("EVAL_LOGFIRE") or os.getenv("LOGFIRE_TOKEN")):
        return
    try:
        import logfire
    except ModuleNotFoundError:
        print(
            "EVAL_LOGFIRE set but logfire isn't installed — run `uv sync --extra trace`. Skipping tracing."
        )
        return
    logfire.configure(
        send_to_logfire="if-token-present",
        service_name="agent-context-workshop-eval",
        environment=os.getenv("LOGFIRE_ENVIRONMENT") or None,  # tag a run for easy querying
        console=(None if os.getenv("EVAL_LOGFIRE_CONSOLE") else False),
    )
    logfire.instrument_pydantic_ai()
    print(
        "logfire tracing on"
        + (" → Logfire UI" if os.getenv("LOGFIRE_TOKEN") else " (local only — no token)")
        + (f" · env={os.getenv('LOGFIRE_ENVIRONMENT')}" if os.getenv("LOGFIRE_ENVIRONMENT") else "")
    )


def usage_of(res):
    u = res.usage() if callable(getattr(res, "usage", None)) else res.usage
    return dict(
        in_tok=getattr(u, "input_tokens", 0) or 0,
        out_tok=getattr(u, "output_tokens", 0) or 0,
        turns=getattr(u, "requests", 0) or 0,
        tool_calls=getattr(u, "tool_calls", 0) or 0,
    )


async def run_one(agent, question, deps=None):
    """Run one agent on one question with a request cap + per-run timeout; a hung/flaky run
    becomes a miss (sentinel), never a whole-run stall."""
    from pydantic_ai.usage import UsageLimits

    t0 = time.perf_counter()
    limits = UsageLimits(
        request_limit=int(os.getenv("EVAL_REQUEST_LIMIT", "80"))
    )  # default 50 starved searches
    try:
        coro = (
            agent.run(question, deps=deps, usage_limits=limits)
            if deps is not None
            else agent.run(question, usage_limits=limits)
        )
        res = await asyncio.wait_for(coro, timeout=float(os.getenv("EVAL_RUN_TIMEOUT", "150")))
        return res, res.output, usage_of(res), time.perf_counter() - t0
    except Exception as e:  # incl. TimeoutError
        return (
            None,
            "",
            dict(in_tok=0, out_tok=0, turns=0, tool_calls=0, error=str(e)[:140]),
            time.perf_counter() - t0,
        )


def setup_graph():
    from context_workshop.graph import GraphTools, build_rust_graph, connect, dedupe_edges, load

    driver = connect(os.getenv("EVAL_NEO4J_URI", "neo4j://localhost:7687"), "neo4j", "workshop123")
    if os.getenv(
        "EVAL_GRAPH_PRELOADED"
    ):  # another process already loaded it — share READ-ONLY, never reset
        with driver.session() as s:
            n = s.run("MATCH (n:Symbol) RETURN count(n) AS n").single()["n"]
        return driver, GraphTools(driver), n, -1
    nodes, edges = [], []
    for crate in CRATES:
        n, e = build_rust_graph(DOC / f"{crate}.json")
        nodes += n
        edges += e
    allow = set(CRATES)
    nodes = list(
        {
            n["qualified_name"]: n for n in nodes if n["qualified_name"].split("::", 1)[0] in allow
        }.values()
    )
    keep = {n["qualified_name"] for n in nodes}
    edges = [e for e in dedupe_edges(edges) if e.src in keep and e.dst in keep]
    load(driver, nodes, edges, reset=True, assert_connected=False)
    return driver, GraphTools(driver), len(nodes), len(edges)


def setup_fs_tree():
    """Mirror the REAL qdrant repo layout (`lib/<crate>/...`) so the graph's repo-relative filepaths
    — e.g. `lib/segment/src/...`, straight from rustdoc — actually resolve when an agent reads them.
    A flattened tree (no `lib/`) 404s every graph path, so the fallback agent distrusts the graph and
    reverts to grep, silently UNDERSTATING the adoption metric. The grep agent is unaffected: the scorer
    matches on basename, and grep just traverses one extra directory level.
    EVAL_FS_FLATTEN=1 rebuilds the old flat layout — kept only to A/B the size of that bug."""
    want_lib = not os.getenv("EVAL_FS_FLATTEN")
    if (FS_ROOT / "lib").is_dir() != want_lib or not FS_ROOT.exists():
        if FS_ROOT.exists():
            shutil.rmtree(FS_ROOT)  # existing layout != requested → rebuild
        for crate in CRATES:
            dst = FS_ROOT / "lib" / crate if want_lib else FS_ROOT / crate
            shutil.copytree(ROOT / "data/raw_repos/qdrant/lib" / crate, dst, symlinks=False)
    return FS_ROOT


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


async def main(sample, out_path, names=None):
    scorer_selftest()
    if not HAS_KEY:
        print("No model key — scorer validated, but live runs need a key. Stopping.")
        return
    _maybe_logfire()
    from pydantic_ai import Agent
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai_backends import LocalBackend, create_console_toolset
    from pydantic_evals import Case, Dataset
    from pydantic_evals.evaluators import Evaluator, EvaluatorContext

    from context_workshop.graph.agent import build_graph_agent

    driver, graph_tools, n_nodes, n_edges = setup_graph()
    setup_fs_tree()
    print(
        f"graph: {n_nodes} nodes / {n_edges} edges | fs tree: {FS_ROOT.name} | model: {AGENT_MODEL}\n"
    )

    fs_toolset = create_console_toolset(include_execute=False)
    fs_deps = FsDeps(backend=LocalBackend(root_dir=str(FS_ROOT)))
    agent_graph = build_graph_agent(AGENT_MODEL, graph_tools)  # A: graph only
    instr_fs = (
        "You answer questions about a Rust codebase with grep/glob/read_file/ls. Find the "
        "answer and cite each definition by file:line. If you can't find it, say so."
    )
    agent_grep = Agent(
        AGENT_MODEL,
        toolsets=[fs_toolset],
        deps_type=FsDeps,
        retries=3,
        model_settings=ModelSettings(temperature=0),
        system_prompt=instr_fs,
    )  # B
    agent_naive = build_fallback_agent(AGENT_MODEL, graph_tools, fs_toolset, nudge=False)  # C naive
    agent_nudged = build_fallback_agent(
        AGENT_MODEL, graph_tools, fs_toolset, nudge=True
    )  # C nudged

    if names:
        questions = [g for g in GOLD if g["name"] in set(names.split(","))]
    elif sample is None:
        questions = GOLD
    else:
        import random as _rnd

        questions = _rnd.Random(0).sample(
            GOLD, min(sample, len(GOLD))
        )  # seeded + representative, not GOLD[:n]

    async def run_question(g: dict) -> dict:
        graph_res, graph_out, graph_usage, _ = await run_one(agent_graph, g["q"])  # A: graph-only
        grep_res, grep_out, grep_usage, _ = await run_one(
            agent_grep, g["q"], deps=fs_deps
        )  # B: grep-only
        out = {
            "graph": graph_out,
            "grep": grep_out,
            "graph_tools": tool_breakdown(graph_res),
            "grep_tools": tool_breakdown(grep_res),
            "graph_usage": graph_usage,
            "grep_usage": grep_usage,
            "naive_tools": None,
            "nudged_tools": None,
        }
        if g["klass"] in ADOPT_CLASSES:  # C: naive vs nudged
            res_n, _, _, _ = await run_one(agent_naive, g["q"], deps=fs_deps)
            res_d, _, _, _ = await run_one(agent_nudged, g["q"], deps=fs_deps)
            out["naive_tools"], out["nudged_tools"] = tool_breakdown(res_n), tool_breakdown(res_d)
        print(
            f"  ✓ {g['name']:<22} graph={'Y' if cites_all(out['graph'], g['anchors']) else 'n'}"
            f" grep={'Y' if cites_all(out['grep'], g['anchors']) else 'n'}",
            flush=True,
        )
        return out

    @dataclass
    class GoldScores(Evaluator):
        """Deterministic gold-anchored capability (bool→assertion) + adoption rate (float→score)."""

        def evaluate(self, ctx: EvaluatorContext) -> dict:
            g, o = ctx.inputs, ctx.output
            r = {
                "graph_hit": cites_all(o["graph"], g["anchors"]),
                "grep_hit": cites_all(o["grep"], g["anchors"]),
            }
            if o["nudged_tools"] is not None:
                na, nu = adoption(o["naive_tools"])[0], adoption(o["nudged_tools"])[0]
                if na is not None:
                    r["naive_adoption"] = na
                if nu is not None:
                    r["nudged_adoption"] = nu
            return r

    dataset = Dataset(
        name="graph-vs-grep",
        cases=[
            Case(name=g["name"], inputs=g, metadata={"klass": g["klass"], "expect": g["expect"]})
            for g in questions
        ],
        evaluators=[GoldScores()],
    )
    report = await dataset.evaluate(
        run_question,
        max_concurrency=int(os.getenv("EVAL_CONCURRENCY", "8")),
        repeat=int(os.getenv("EVAL_REPEAT", "1")),
    )
    driver.close()
    print(f"\npydantic-evals: {len(report.cases)} case-runs complete")

    # ---- aggregate by question across `repeat` runs (averages out n=1 noise) → committed cache ----
    byname = defaultdict(list)
    for c in report.cases:
        byname[c.inputs["name"]].append(c.output)
    records, adopt = [], []
    for name, outs in byname.items():
        g = next(x for x in GOLD if x["name"] == name)
        records.append(
            dict(
                name=name,
                klass=g["klass"],
                expect=g["expect"],
                win=g.get("win"),
                runs=len(outs),
                graph=dict(
                    hit=_mean([1.0 if cites_all(o["graph"], g["anchors"]) else 0.0 for o in outs]),
                    recall=_mean([set_recall(o["graph"], g.get("dependents")) for o in outs]),
                    tool_calls=_mean([o["graph_usage"]["tool_calls"] for o in outs]),
                    in_tok=_mean([o["graph_usage"]["in_tok"] for o in outs]),
                ),
                grep=dict(
                    hit=_mean([1.0 if cites_all(o["grep"], g["anchors"]) else 0.0 for o in outs]),
                    recall=_mean([set_recall(o["grep"], g.get("dependents")) for o in outs]),
                    tool_calls=_mean([o["grep_usage"]["tool_calls"] for o in outs]),
                    in_tok=_mean([o["grep_usage"]["in_tok"] for o in outs]),
                ),
            )
        )
        if outs[0]["nudged_tools"] is not None:
            adopt.append(
                dict(
                    name=name,
                    klass=g["klass"],
                    runs=len(outs),
                    naive=dict(adoption=_mean([adoption(o["naive_tools"])[0] for o in outs])),
                    nudged=dict(adoption=_mean([adoption(o["nudged_tools"])[0] for o in outs])),
                )
            )

    # ---- summaries: capability · efficiency (the real win) · completeness · adoption · consistency ----
    print("\n=== CAPABILITY (graph vs grep), per class — repeat-averaged hit-rate × n ===")
    for k in ("typedep", "collision", "private", "control"):
        rs = [r for r in records if r["klass"] == k]
        if rs:
            print(
                f"  {k:<10} graph {round(sum(r['graph']['hit'] for r in rs), 1)}/{len(rs)}   "
                f"grep {round(sum(r['grep']['hit'] for r in rs), 1)}/{len(rs)}"
            )
    print("\n=== EFFICIENCY (avg input tokens / question) — same answers, far less context ===")
    graph_tok = round(sum(r["graph"]["in_tok"] for r in records) / len(records))
    grep_tok = round(sum(r["grep"]["in_tok"] for r in records) / len(records))
    print(f"  graph {graph_tok:>7}   grep {grep_tok:>7}   ({round(grep_tok / graph_tok, 1)}x)")
    td = [r for r in records if r["klass"] == "typedep"]
    if td:
        print("\n=== COMPLETENESS (typedep set-recall — fraction of gold dependents named) ===")
        print(
            f"  graph {_mean([r['graph']['recall'] for r in td])}   grep {_mean([r['grep']['recall'] for r in td])}"
        )
    if adopt:
        print("\n=== ADOPTION (graph-tool share of code lookups) ===")
        print(
            f"  naive {_mean([a['naive']['adoption'] for a in adopt])}  ->  "
            f"nudged {_mean([a['nudged']['adoption'] for a in adopt])}  (n={len(adopt)})"
        )

    rep_k = int(os.getenv("EVAL_REPEAT", "1"))
    if (
        rep_k > 1
    ):  # determinism: grep re-derives connections each run (noisy); the graph looked them up once
        print(
            f"\n=== CONSISTENCY across k={rep_k} runs · pass@k = ever right · pass^k = right EVERY run ==="
        )
        for side in ("graph", "grep"):
            atk = sum(1 for r in records if (r[side]["hit"] or 0) > 0)
            powk = sum(1 for r in records if (r[side]["hit"] or 0) == 1.0)
            print(
                f"  {side:<6} pass@{rep_k} {atk}/{len(records)}   pass^{rep_k} {powk}/{len(records)}"
            )
        for k in ("typedep", "collision"):
            rs = [r for r in records if r["klass"] == k]
            gp = sum(1 for r in rs if (r["graph"]["hit"] or 0) == 1.0)
            pp = sum(1 for r in rs if (r["grep"]["hit"] or 0) == 1.0)
            print(f"    pass^{rep_k} [{k}]  graph {gp}/{len(rs)}   grep {pp}/{len(rs)}")

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(
            json.dumps(
                dict(model=AGENT_MODEL, repeat=rep_k, records=records, adoption=adopt), indent=1
            )
        )
        print("\nwrote", out_path)


async def nudge_ablation(out_path):
    """Adoption A/B/C: naive vs nudged vs nudged_v2 on the SAME questions/k — does a harder prompt
    move the ceiling? Writes a separate file; never touches the canonical cache."""
    scorer_selftest()
    if not HAS_KEY:
        print("No model key — live runs need a key. Stopping.")
        return
    _maybe_logfire()
    from pydantic_ai_backends import LocalBackend, create_console_toolset

    driver, graph_tools, n_nodes, n_edges = setup_graph()
    setup_fs_tree()
    fs_toolset = create_console_toolset(include_execute=False)
    fs_deps = FsDeps(backend=LocalBackend(root_dir=str(FS_ROOT)))
    arms = {
        "naive": build_fallback_agent(AGENT_MODEL, graph_tools, fs_toolset, nudge=False),
        "nudged": build_fallback_agent(AGENT_MODEL, graph_tools, fs_toolset, nudge=True),
        "nudged_v2": build_fallback_agent(
            AGENT_MODEL, graph_tools, fs_toolset, nudge=True, prompt=NUDGED_V2_PROMPT
        ),
    }
    qs = [g for g in GOLD if g["klass"] in ADOPT_CLASSES]
    repeat = int(os.getenv("EXP_REPEAT", "1"))
    sem = asyncio.Semaphore(int(os.getenv("EVAL_CONCURRENCY", "6")))
    print(
        f"graph {n_nodes}n/{n_edges}e | model {AGENT_MODEL} | {len(qs)} questions × {len(arms)} arms × k={repeat}\n",
        flush=True,
    )
    per = defaultdict(lambda: defaultdict(list))

    async def one(arm, agent, g):
        async with sem:
            res, _, _, _ = await run_one(agent, g["q"], deps=fs_deps)
            a = adoption(tool_breakdown(res))[0]
            per[arm][g["name"]].append(a)
            print(f"  {arm:<9} {g['name']:<22} adoption={a}", flush=True)

    await asyncio.gather(
        *[one(arm, agent, g) for arm, agent in arms.items() for g in qs for _ in range(repeat)]
    )
    driver.close()
    records = {arm: {name: _mean(runs) for name, runs in per[arm].items()} for arm in arms}

    def overall(arm):
        return _mean(list(records[arm].values()))

    def by_class(arm, klass):
        names = {g["name"] for g in qs if g["klass"] == klass}
        return _mean([v for n, v in records[arm].items() if n in names])

    print(
        "\n=== ADOPTION CEILING — graph-tool share, same questions/k, prompt is the only change ==="
    )
    print(f"  {'arm':<11}{'overall':>9}{'typedep':>10}{'collision':>11}{'control':>9}")
    for arm in arms:
        print(
            f"  {arm:<11}{str(overall(arm)):>9}{str(by_class(arm, 'typedep')):>10}"
            f"{str(by_class(arm, 'collision')):>11}{str(by_class(arm, 'control')):>9}"
        )
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(
            json.dumps(
                dict(
                    model=AGENT_MODEL,
                    repeat=repeat,
                    n_questions=len(qs),
                    overall={arm: overall(arm) for arm in arms},
                    by_class={arm: {k: by_class(arm, k) for k in ADOPT_CLASSES} for arm in arms},
                    per_question=records,
                ),
                indent=1,
            )
        )
        print("\nwrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=3)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--names", default=None, help="comma-separated gold names for a diverse smoke")
    ap.add_argument(
        "--nudge-ablation", action="store_true", help="naive vs nudged vs nudged_v2 adoption"
    )
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.nudge_ablation:
        asyncio.run(nudge_ablation(a.out))
    else:
        asyncio.run(main(None if a.all else a.sample, a.out, names=a.names))
