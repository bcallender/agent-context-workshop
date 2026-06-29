# tests/graph/test_rust_edges_tier_a.py
import json
from pathlib import Path

from context_workshop.graph.rust import build_rust_graph, extract_edges
from context_workshop.parsers import load_rust_rustdoc

FIX = Path(__file__).parent.parent / "fixtures" / "rustdoc_min.json"


def _edges():
    data = json.loads(FIX.read_text())
    return extract_edges(load_rust_rustdoc(FIX), data)


def test_contains_links_module_to_item():
    es = _edges()
    assert any(
        e.type == "CONTAINS" and e.src == "mycrate" and e.dst == "mycrate::inner::Thing" for e in es
    )


def test_has_method_links_type_to_method():
    es = _edges()
    assert any(
        e.type == "HAS_METHOD"
        and e.src == "mycrate::inner::Thing"
        and e.dst == "mycrate::inner::Thing::new"
        for e in es
    )


def test_reexports_edge_points_module_to_canonical():
    es = _edges()
    assert any(
        e.type == "REEXPORTS" and e.src == "mycrate" and e.dst == "mycrate::inner::Thing"
        for e in es
    )


def test_contains_excludes_reexport_aliases():
    """CONTAINS must not emit the alias path; only structural members."""
    es = _edges()
    assert not any(e.type == "CONTAINS" and e.dst == "mycrate::Thing" for e in es)


def test_build_rust_graph_returns_nodes_and_edges():
    nodes, edges = build_rust_graph(FIX)
    assert any(n["qualified_name"] == "mycrate::inner::Thing" for n in nodes)
    assert all(e.type in {"CONTAINS", "HAS_METHOD", "IMPLEMENTS", "REEXPORTS"} for e in edges)
