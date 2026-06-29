"""Deterministic, gold-anchored scorer for the graph-vs-grep eval.

No LLM judge: an answer scores a hit only if it NAMES the expected symbol (crate-guarded,
negation-aware) and cites it near the right file:line — in either prose form (`posting_list.rs:12`,
`line 12`) or the graph tools' native `line_start: 12`. The point of a deterministic ruler is that
you can measure *reliability* with it; an LLM judge is itself non-deterministic, so it can't.
"""

from __future__ import annotations

import re


def _line_near(text, basename, line):
    for m in re.finditer(re.escape(basename), text, re.IGNORECASE):
        pre = text[max(0, m.start() - 18) : m.start()].lower()
        if any(w in pre for w in ("not ", "n't", "isn", "aren", "rather than", "instead of")):
            continue
        win = text[m.end() : m.end() + 60]
        md_ = re.match(r"[`'\")\]]*\s*[:#@]L?\s*(\d+)", win)
        if md_ and abs(int(md_.group(1)) - line) <= 1:
            return True
        # 'line 27' / 'lines 27' AND the graph tools' native 'line_start: 16' / '(line_start=16)'
        for wm in re.finditer(r"\bline(?:_start|s)?\b[^\d]{0,8}(\d+)", win, re.IGNORECASE):
            if abs(int(wm.group(1)) - line) <= 1:
                return True
    return False


def _one_anchor(text, anchor):
    t = text or ""
    if anchor["symbol"].lower() not in t.lower():
        return False
    if anchor.get("crate") and anchor["crate"].lower() not in t.lower():
        return False
    if anchor.get("mode") == "named":
        return True
    return _line_near(t, anchor["basename"], anchor["line"])


def cites_all(text, anchors):
    """True only if the answer satisfies EVERY anchor (named + crate-guarded + located)."""
    return all(_one_anchor(text, anchor) for anchor in anchors)


def set_recall(text, dependents):
    """For typedep: fraction of DISTINCT gold dependents (by leaf) named — word-boundary, no over-count."""
    if not dependents:
        return None
    t = text or ""
    leaves = sorted(
        set(d.split("::")[-1] for d in dependents)
    )  # dedupe duplicate leaves (e.g. two `Metadata`)
    hit = sum(1 for leaf in leaves if re.search(rf"\b{re.escape(leaf)}\b", t))
    return round(hit / len(leaves), 2)


def scorer_selftest():
    """Unit-test the ruler before trusting any number it produces."""
    S = {"basename": "posting_list.rs", "line": 12, "symbol": "PostingList", "crate": "sparse"}
    assert cites_all(
        "sparse `PostingList`:\n- **File**: `sparse/index/posting_list.rs`\n- **Line**: 12", [S]
    )
    assert cites_all("the sparse PostingList at posting_list.rs:12", [S])
    assert not cites_all("PostingList at posting_list.rs:12", [S])  # crate missing
    assert not cites_all("sparse PostingList is NOT at posting_list.rs:12", [S])  # negated
    # graph tools cite in their native 'line_start: N' form — scorer must read it (was biased against graph)
    assert cites_all(
        "posting_list::view::PostingListView — filepath: lib/posting_list/src/view.rs, line_start: 16",
        [{"basename": "view.rs", "line": 16, "symbol": "PostingListView", "crate": "posting_list"}],
    )
    assert cites_all(
        "sparse PostingList — lib/sparse/src/index/posting_list.rs (line_start: 12)", [S]
    )
    assert (
        set_recall(
            "uses PostingBuilder and PostingListView",
            ["a::PostingBuilder", "b::PostingListView", "c::Missing"],
        )
        == 0.67
    )
    print("scorer self-test passed")
