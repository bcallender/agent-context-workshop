# Agent Context Workshop

**A context layer for coding agents — built, then measured.**

Most coding agents explore a codebase by grepping it. This workshop builds the alternative: a
**code knowledge graph** an agent can traverse instead — then runs an honest eval to see whether it
actually helps, and whether the agent *uses* it.

The worked example is [**qdrant**](https://github.com/qdrant/qdrant) (a real Rust vector database). We
extract its structure into a Neo4j graph and give an agent graph tools (`search`, `blast_radius`,
`implementors`, …). Then we pit a **graph agent** against a **grep agent** on 30 gold-verified questions.

The honest result: on single-shot accuracy they roughly **tie** (graph 21/30, grep 19/30). The graph wins
on what matters in production — **determinism** (right on *every* run: graph 19/30 vs grep 11/30, and 12/15
vs 6/15 on relationship questions — grep re-derives the connections each run and flips), **efficiency**
(~3× fewer input tokens), and the metric nobody reports: **adoption** (does the agent reach for the graph
at all — **34% → 72%** with the right nudge).

## The two mental models

**Three *rungs* of building the context layer** (each notebook walks them):

| Rung | What | How | Determinism |
|---|---|---|---|
| 0 · syntactic | symbols, spans | tree-sitter | deterministic |
| 1 · resolution | types, impls, edges | rustdoc JSON | deterministic |
| 2 · meaning | intent, stability | fenic + an LLM | model-backed, cached |

**Three *levels* of context engineering** (what the eval compares): **L1** grep → **L2** index + search →
**L3** graph traversal.

## Quickstart

Prereqs: [`uv`](https://docs.astral.sh/uv/), Docker (optional — only for notebook 01's graph), and an
[OpenRouter key](https://openrouter.ai/keys) (optional — only for *live* LLM calls; the eval is cached).

```bash
uv sync                       # install (slim — one provider, via OpenRouter)
scripts/setup_data.sh         # hydrate the committed qdrant seed (~2MB) into data/
cp .env.example .env          # add OPENROUTER_API_KEY for live calls (optional)
uv run jupyter lab
```

Then — **new here? jump to notebook 02** (the eval; no Docker, no key needed). The full set, in order:

- **`notebooks/00_start_here.ipynb`** — a 30-second preflight: confirms your install + data are ready and routes you. Run it first.
- **`notebooks/01_posting_list_context.ipynb`** — build the graph and query it. Rungs 0/1/2 run anywhere; Level 3 needs Neo4j: `docker compose up -d`.
- **`notebooks/02_does_the_graph_beat_grep.ipynb`** — ⭐ **the eval — start here.** Runs with **no Docker and no key** (cache-first).
- **`notebooks/03_python_griffe_resolution.ipynb`** — optional Python coda: griffe resolves a package statically (the "no compiler" case). Keyless-safe.
- **`notebooks/04_rung2_fenic_coda.ipynb`** — optional fenic Rung-2 coda (intent from comments). Renders example output without a key.

**No local setup?** Run in Colab (the first cell clones + installs). **Start with nb02 — no key needed:**
[notebook 01](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/01_posting_list_context.ipynb) *(Level 3 needs a Neo4j — point it at free [Aura](https://console.neo4j.io); see [SETUP.md](SETUP.md))* ·
[notebook 02](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/02_does_the_graph_beat_grep.ipynb) ·
[notebook 03](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/03_python_griffe_resolution.ipynb) ·
[notebook 04](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/04_rung2_fenic_coda.ipynb)

**One key, any model.** The agent *and* fenic both route through OpenRouter, so a single
`OPENROUTER_API_KEY` lets you pick any model (`openrouter:anthropic/claude-sonnet-4`,
`openrouter:openai/gpt-5-mini`, …) via the `AGENT_MODEL` env var. See [`SETUP.md`](SETUP.md).

## Repository map

```text
notebooks/                     # 00 start-here · 01 build+query · 02 eval · 03 python · 04 fenic
src/context_workshop/
  parsers/                     # Rung 0/1 extraction (tree-sitter, rustdoc, griffe) → typed Symbol rows
  graph/                       # nodes/edges, Neo4j loader, GraphTools, the graph agent
  eval/                        # the graph-vs-grep harness: corpus · scorer · nudges · harness
tests/                         # unit + integration tests (incl. the deterministic scorer)
assets/                        # committed qdrant seed: gzipped rustdoc JSON + 4 crates' source
data/eval/                     # committed eval cache (what notebook 02 renders) — no key needed
scripts/                       # setup_data.sh (hydrate) · regenerate_data.sh (rebuild from qdrant)
```

## License

Apache-2.0 — see [`LICENSE`](LICENSE). The example codebase is qdrant (Apache-2.0); see
[`ATTRIBUTION.md`](ATTRIBUTION.md).
