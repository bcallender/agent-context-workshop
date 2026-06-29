# Setup

Five minutes if you do the two **ahead-of-time** steps below before the session (conference wifi will not
love 40 people pulling a Docker image at once).

## Ahead of time (please!)

1. **Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/).**
2. **Pre-pull the Neo4j image** (only needed for notebook 01's graph):
   ```bash
   docker pull neo4j:5.26.27
   ```
3. *(Optional)* Grab an **[OpenRouter key](https://openrouter.ai/keys)** if you want to run LLM calls live.
   The eval notebook works fully **without** one.

## In the room

```bash
git clone <this-repo> && cd agent-context-workshop
uv sync                       # install (slim — one provider via OpenRouter)
scripts/setup_data.sh         # hydrate the committed qdrant seed (~2MB) into data/
cp .env.example .env          # then paste your OPENROUTER_API_KEY (optional)
uv run jupyter lab
```

## No local setup? Open it in Colab

The cache-first notebooks run in Colab with **zero install** — the first cell clones the repo, installs it,
and hydrates the data. **New here? Start with notebook 02** (the eval — no Docker, no key):

- **Notebook 01** (the build) — full thing in Colab if you point it at a free [Aura](https://console.neo4j.io) (see below): [Open in Colab](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/01_posting_list_context.ipynb)
- **Notebook 02** (the eval) — ⭐ no Docker, no key, **start here**: [Open in Colab](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/02_does_the_graph_beat_grep.ipynb)
- **Notebook 03** (Python / griffe): [Open in Colab](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/03_python_griffe_resolution.ipynb)
- **Notebook 04** (fenic Rung-2) — renders an example without a key: [Open in Colab](https://colab.research.google.com/github/bcallender/agent-context-workshop/blob/main/notebooks/04_rung2_fenic_coda.ipynb)

## What needs what

| Notebook | Docker / Neo4j | API key |
|---|---|---|
| 01 · build + query | only for **Level 3** (`docker compose up -d`) | only for the live agent cells |
| **02 · the eval** | ❌ no | ❌ no — fully cached, ⭐ **start here** |
| 03 · Python coda | no | only for the fenic enrichment cell (renders an example without one) |
| 04 · fenic coda | no | only to run live (renders example output without one) |

## Neo4j for notebook 01 — Docker or Aura (no Docker)

Notebook 01's **Level 3** (loading + traversing the graph) needs a Neo4j. Either works — nb01 reads the
connection straight from your environment, so there's no code change:

- **Docker (default):** `docker compose up -d` (creds `neo4j` / `workshop123`).
- **No Docker? Free [Neo4j Aura](https://console.neo4j.io):** create a free instance (~2 min), then set these
  in `.env` (or your shell, or a Colab cell) — that's the only change:
  ```bash
  NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=your-aura-password
  ```
  Aura is cloud-hosted, so it's lighter than Docker and also lets the **full nb01 build run from Colab**.

## Models — one key, any model

The agent **and** fenic both route through OpenRouter, so a single `OPENROUTER_API_KEY` unlocks any model.
Choose one with the `AGENT_MODEL` env var (default `openrouter:openai/gpt-5.4-mini`):

```bash
export AGENT_MODEL="openrouter:anthropic/claude-sonnet-4"   # or openai/gpt-5-mini, qwen/..., etc.
```

## Verify

```bash
uv run pytest -q                                    # all green
uv run jupyter nbconvert --to notebook --execute \
  --inplace notebooks/02_does_the_graph_beat_grep.ipynb   # renders the eval (no Docker/key)
```

## Troubleshooting

- **`assert CRATE.exists()` in notebook 01** → you skipped `scripts/setup_data.sh`.
- **Notebook 01 Level 3 cells skip** → no Neo4j reachable: `docker compose up -d` (creds `neo4j` / `workshop123`), or point `NEO4J_URI`/`NEO4J_PASSWORD` at a free Aura instance (see above).
- **Live agent cells do nothing** → no `OPENROUTER_API_KEY` in `.env` (expected; the cache still renders).
- **Re-run the full eval** (needs the 5th `segment` crate): `scripts/regenerate_data.sh` (Rust nightly), then
  `uv run python -m context_workshop.eval.harness --all --out data/eval/graph_vs_grep_cache.json`.
