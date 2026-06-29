from context_workshop.graph.schema import EDGE_TYPES, Edge, dedupe_edges, edge_rows


def test_edge_rows_are_jsonable_dicts():
    e = Edge(
        src="c::A",
        dst="c::B",
        type="CALLS",
        rung="calls",
        extractor="rust-analyzer-scip",
        files=["a.rs"],
        lines=[3],
    )
    [row] = edge_rows([e])
    assert row["src"] == "c::A" and row["type"] == "CALLS" and row["count"] == 1
    assert "CALLS" in EDGE_TYPES and "IMPLEMENTS" in EDGE_TYPES


def test_dedupe_merges_sites_and_counts():
    a = Edge(
        src="c::f",
        dst="c::g",
        type="CALLS",
        rung="calls",
        extractor="scip",
        files=["f.rs"],
        lines=[1],
    )
    b = Edge(
        src="c::f",
        dst="c::g",
        type="CALLS",
        rung="calls",
        extractor="scip",
        files=["f.rs"],
        lines=[9],
    )
    other = Edge(src="c::f", dst="c::h", type="CALLS", rung="calls", extractor="scip")
    out = dedupe_edges([a, b, other])
    assert len(out) == 2
    merged = [e for e in out if e.dst == "c::g"][0]
    assert merged.count == 2 and merged.lines == [1, 9] and merged.files == ["f.rs", "f.rs"]


def test_dedupe_keeps_return_and_param_to_same_type_distinct():
    ret = Edge(
        src="c::f",
        dst="c::T",
        type="RETURNS",
        rung="resolution",
        extractor="rustdoc-json",
        position="return",
    )
    arg = Edge(
        src="c::f",
        dst="c::T",
        type="TAKES",
        rung="resolution",
        extractor="rustdoc-json",
        position="param",
    )
    assert len(dedupe_edges([ret, arg])) == 2


def test_dedupe_synthetic_flag_is_false_when_any_contributing_edge_is_genuine():
    # A derive impl (synthetic=True) and a hand-written impl (synthetic=False) for the same key
    # must produce synthetic=False — a "genuine" site beats "all synthetic".
    syn = Edge(
        src="c::MyType",
        dst="c::Debug",
        type="IMPLEMENTS",
        rung="resolution",
        extractor="rustdoc-json",
        synthetic=True,
    )
    real = Edge(
        src="c::MyType",
        dst="c::Debug",
        type="IMPLEMENTS",
        rung="resolution",
        extractor="rustdoc-json",
        synthetic=False,
    )
    [merged] = dedupe_edges([syn, real])
    assert merged.synthetic is False


def test_dedupe_synthetic_flag_stays_true_when_all_edges_are_synthetic():
    a = Edge(
        src="c::MyType",
        dst="c::Clone",
        type="IMPLEMENTS",
        rung="resolution",
        extractor="rustdoc-json",
        synthetic=True,
    )
    b = Edge(
        src="c::MyType",
        dst="c::Clone",
        type="IMPLEMENTS",
        rung="resolution",
        extractor="rustdoc-json",
        synthetic=True,
    )
    [merged] = dedupe_edges([a, b])
    assert merged.synthetic is True
