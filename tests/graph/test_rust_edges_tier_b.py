# tests/graph/test_rust_edges_tier_b.py
import json
from pathlib import Path

from context_workshop.graph.rust import extract_edges
from context_workshop.parsers import load_rust_rustdoc

FIX = Path(__file__).parent.parent / "fixtures" / "rustdoc_edges.json"


def _edges():
    data = json.loads(FIX.read_text())
    return extract_edges(load_rust_rustdoc(FIX), data)


def test_returns_and_takes_named_types():
    es = _edges()
    assert any(
        e.type == "RETURNS"
        and e.src == "edgecrate::Widget::make"
        and e.dst == "edgecrate::Widget"
        and e.position == "return"
        for e in es
    )
    assert any(
        e.type == "TAKES"
        and e.src == "edgecrate::Widget::make"
        and e.dst == "edgecrate::Part"
        and e.position == "param"
        for e in es
    )


def test_implements_trait():
    es = _edges()
    assert any(
        e.type == "IMPLEMENTS" and e.src == "edgecrate::Widget" and e.dst == "edgecrate::Draw"
        for e in es
    )


def test_has_field_type():
    es = _edges()
    assert any(
        e.type == "HAS_FIELD"
        and e.src == "edgecrate::Widget"
        and e.dst == "edgecrate::Part"
        and e.position == "field"
        for e in es
    )


def test_generic_return_recurses_into_args():
    es = _edges()
    # wrap() -> Holder<Part>: an edge to the outer Holder AND the inner Part (wrapper=Holder)
    assert any(
        e.type == "RETURNS" and e.dst == "edgecrate::Holder" and e.wrapper is None for e in es
    )
    inner = [
        e
        for e in es
        if e.type == "RETURNS" and e.dst == "edgecrate::Part" and e.src == "edgecrate::wrap"
    ]
    assert inner and inner[0].wrapper == "Holder"
