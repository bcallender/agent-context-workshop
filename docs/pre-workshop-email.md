# Pre-workshop setup email (draft)

**Subject: 2 things to install before the Agent Context Workshop**

Hi all — looking forward to the workshop. It's hands-on, so two quick installs ahead of time will save us
fighting conference wifi in the room:

1. **Install `uv`** (the Python runner): <https://docs.astral.sh/uv/getting-started/installation/>
2. **Pre-pull the Neo4j Docker image** (used in one notebook):
   ```
   docker pull neo4j:5.26.27
   ```
   No Docker? No problem — the main eval notebook needs neither Docker nor a key. You'll just skip the
   graph-loading section of notebook 01.

**Optional, if you want to run live LLM calls:** grab an OpenRouter key at <https://openrouter.ai/keys>
(a couple of dollars of credit is plenty). One key works for everything — you pick the model. Everything
also runs from a committed cache **without** a key, so this is genuinely optional.

That's it. We'll clone the repo and run `uv sync && scripts/setup_data.sh` together at the start. Full
instructions live in `SETUP.md` in the repo.

See you there,
Brandon
