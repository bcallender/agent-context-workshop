"""Graph-vs-grep eval: a deterministic, no-LLM-judge harness over the 30-question corpus.

- `corpus.GOLD` — the questions + verified gold anchors.
- `scorer` — the deterministic, gold-anchored checker (the ruler).
- `nudges` — naive/nudged prompts + the both-tools fallback agent (the adoption lever).
- `harness` — the run that produces the committed cache (`python -m context_workshop.eval.harness`).
"""

from context_workshop.eval.corpus import GOLD
from context_workshop.eval.nudges import (
    NAIVE_PROMPT,
    NUDGED_PROMPT,
    NUDGED_V2_PROMPT,
    adoption,
    build_fallback_agent,
    tool_breakdown,
)
from context_workshop.eval.scorer import cites_all, scorer_selftest, set_recall

__all__ = [
    "GOLD",
    "cites_all",
    "set_recall",
    "scorer_selftest",
    "NAIVE_PROMPT",
    "NUDGED_PROMPT",
    "NUDGED_V2_PROMPT",
    "adoption",
    "build_fallback_agent",
    "tool_breakdown",
]
