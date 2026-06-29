# AGENTS.md

Operating guide for AI agents (and humans) working in this repository.

## What this is

A hands-on workshop that **builds a context layer for a coding agent and then measures it**. The worked
example is a code knowledge graph over [qdrant](https://github.com/qdrant/qdrant) (Rust), and an eval
that compares an agent traversing that graph against an agent that greps.

The organizing idea is three **rungs** of building the layer — keep them separate, that separation is the
lesson:

1. **Rung 0 — syntactic** (`parsers/`, tree-sitter): symbols and spans. Deterministic, no model.
2. **Rung 1 — resolution** (`parsers/` rustdoc JSON → `graph/`): types, impls, typed edges. Deterministic.
3. **Rung 2 — meaning** (`notebooks/04`, fenic + an LLM): intent from comments, stability. Model-backed, **cached**. (`notebooks/03` is the Python/griffe Rung-1 coda — resolution without a compiler.)

Rungs 0–1 are where the graph earns its keep without ever calling a model. Rung 2 is optional and the
first thing to cut.

## Where things live

- `src/context_workshop/parsers/` — Rung 0/1 extraction → typed `Symbol` rows (plain dicts; the notebook decides where they land).
- `src/context_workshop/graph/` — nodes/edges, the Neo4j loader, `GraphTools`, and `build_graph_agent`.
- `src/context_workshop/eval/` — the graph-vs-grep harness: `corpus` (30 gold questions) · `scorer` (deterministic checker) · `nudges` (prompts + adoption lever) · `harness` (the run).
- `notebooks/` — the workshop surface (00 start-here · 01 build+query · 02 eval · 03 python · 04 fenic).
- `assets/` + `scripts/setup_data.sh` — the committed qdrant seed and how it hydrates into `data/`.
- `data/eval/` — the committed eval cache notebook 02 renders (no key/Docker needed).

## Conventions

- **Models route through OpenRouter.** One `OPENROUTER_API_KEY`; pick a model via `AGENT_MODEL`
  (e.g. `openrouter:openai/gpt-5.4-mini`). Don't reintroduce provider-specific keys.
- **Separate deterministic from model-backed.** Rung 0/1 must stay model-free and reproducible. Anything
  that calls a model is Rung 2 and its output is cached as a build artifact.
- **The eval scorer is deterministic — no LLM judge.** You can't measure reliability with a
  non-deterministic ruler. Unit-test the scorer (`tests/eval/test_scorer.py`) before trusting any number.
- **Report per class, name the losses.** The eval splits typedep / collision / private / control, and the
  honest losses (the graph can't see private internals) are the roadmap, not something to hide.

## Running

```bash
uv sync && scripts/setup_data.sh
uv run pytest                              # unit + integration
uv run jupyter lab                         # notebooks (02 needs nothing; 01 L3 needs `docker compose up -d`)
uv run python -m context_workshop.eval.harness --all --out data/eval/graph_vs_grep_cache.json   # re-run the eval
```
