import os
from pathlib import Path

import pytest

from context_workshop.graph.loader import connect, load
from context_workshop.graph.rust import build_rust_graph
from context_workshop.graph.tools import GraphTools

pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_TEST_URI"), reason="needs NEO4J_TEST_URI")
FIX = Path(__file__).parent.parent / "fixtures" / "rustdoc_edges.json"


def test_blast_radius_and_implementors():
    with connect(
        os.environ["NEO4J_TEST_URI"],
        password=os.getenv("NEO4J_TEST_PASSWORD", "workshop123"),
    ) as drv:
        load(drv, *build_rust_graph(FIX), reset=True)
        gt = GraphTools(drv)
        deps = {r["qualified_name"] for r in gt.blast_radius("edgecrate::Part", depth=2)}
        impls = {r["qualified_name"] for r in gt.implementors("edgecrate::Draw")}
    assert "edgecrate::Widget" in deps
    assert "edgecrate::Widget" in impls
