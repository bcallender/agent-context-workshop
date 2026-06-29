import pytest

from context_workshop.graph.loader import (
    NODE_MERGE_CYPHER,
    edge_groups,
    edge_merge_cypher,
    node_batches,
)
from context_workshop.graph.schema import Edge


def test_node_batches_chunk():
    nodes = [{"qualified_name": f"c::{i}", "kind": "function"} for i in range(2500)]
    sizes = [len(b) for b in node_batches(nodes, size=1000)]
    assert sizes == [1000, 1000, 500]
    assert "MERGE" in NODE_MERGE_CYPHER and "qualified_name" in NODE_MERGE_CYPHER


def test_edge_groups_split_by_type_and_safe_type_name():
    es = [
        Edge(src="a", dst="b", type="CALLS", rung="calls", extractor="scip"),
        Edge(src="a", dst="c", type="IMPLEMENTS", rung="resolution", extractor="rustdoc-json"),
    ]
    groups = edge_groups(es)
    assert set(groups) == {"CALLS", "IMPLEMENTS"}
    assert groups["CALLS"][0]["src"] == "a"
    # relationship type is interpolated (validated against EDGE_TYPES), never user-parameterized
    assert "CALLS" in edge_merge_cypher("CALLS")


def test_edge_merge_cypher_rejects_unknown_type():
    with pytest.raises(ValueError, match="NOT_A_TYPE"):
        edge_merge_cypher("NOT_A_TYPE")
