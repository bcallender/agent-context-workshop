"""The deterministic scorer is the ruler — unit-test it before trusting any eval number."""

from context_workshop.eval.scorer import cites_all, set_recall

S = {"basename": "posting_list.rs", "line": 12, "symbol": "PostingList", "crate": "sparse"}


def test_cites_all_file_line():
    assert cites_all("sparse `PostingList` at posting_list.rs:12", [S])


def test_cites_all_requires_crate():
    assert not cites_all("PostingList at posting_list.rs:12", [S])  # crate missing


def test_cites_all_rejects_negation():
    assert not cites_all("sparse PostingList is NOT at posting_list.rs:12", [S])


def test_cites_all_reads_graph_line_start_form():
    a = {"basename": "view.rs", "line": 16, "symbol": "PostingListView", "crate": "posting_list"}
    assert cites_all("posting_list::view::PostingListView — view.rs, line_start: 16", [a])


def test_set_recall_dedupes_and_word_boundaries():
    assert (
        set_recall(
            "uses PostingBuilder and PostingListView",
            ["a::PostingBuilder", "b::PostingListView", "c::Missing"],
        )
        == 0.67
    )
