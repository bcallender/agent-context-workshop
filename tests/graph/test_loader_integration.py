"""Integration tests for load() — require a live Neo4j instance.

Set NEO4J_TEST_URI (e.g. neo4j://localhost:7687) to run; skipped otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from context_workshop.graph.loader import connect, load
from context_workshop.graph.rust import build_rust_graph

pytestmark = pytest.mark.skipif(
    not os.getenv("NEO4J_TEST_URI"),
    reason="set NEO4J_TEST_URI (e.g. neo4j://localhost:7687) to run loader integration tests",
)
FIX = Path(__file__).parent.parent / "fixtures" / "rustdoc_edges.json"


def _driver():
    return connect(
        os.environ["NEO4J_TEST_URI"],
        password=os.getenv("NEO4J_TEST_PASSWORD", "workshop123"),
    )


def test_load_then_blast_radius_finds_dependents():
    nodes, edges = build_rust_graph(FIX)
    with _driver() as drv:
        stats = load(drv, nodes, edges, reset=True)
        # (1) Every node is connected — no qualified_name key mismatch.
        assert stats["isolated"] == 0, f"isolated={stats['isolated']} nodes after load"
        with drv.session() as s:
            # (2) Blast-radius: Part is used by Widget (HAS_FIELD) and Widget::make (TAKES).
            rows = s.run(
                "MATCH (t:Symbol {qualified_name:'edgecrate::Part'})<-[*1..2]-(d) "
                "RETURN DISTINCT d.qualified_name AS qn"
            ).data()
            deps = {r["qn"] for r in rows}
            assert "edgecrate::Widget" in deps, f"Widget missing from {deps}"
            assert "edgecrate::Widget::make" in deps, f"Widget::make missing from {deps}"

            # (3) A CONTAINS edge from the crate root loaded (proves crate node + root edges match).
            contains_rows = s.run(
                "MATCH (:Symbol {qualified_name:'edgecrate'})-[:CONTAINS]->(d) "
                "RETURN d.qualified_name AS qn"
            ).data()
            contains_qns = {r["qn"] for r in contains_rows}
            assert "edgecrate::Widget" in contains_qns, (
                f"Expected CONTAINS edge edgecrate->Widget, got: {contains_qns}"
            )

            # (4) The crate root node carries the :Crate dynamic label (proves SET n:$(kind_label)).
            label_rows = s.run(
                "MATCH (n:Symbol:Crate {qualified_name:'edgecrate'}) RETURN n.qualified_name AS qn"
            ).data()
            assert len(label_rows) == 1, (
                f"Expected 1 :Symbol:Crate node for 'edgecrate', got {len(label_rows)}"
            )

            # (5) Capitalized :Struct label works — Widget/Part/Holder are structs.
            struct_count = s.run("MATCH (n:Struct) RETURN count(n) AS c").single()["c"]
            assert struct_count > 0, (
                f"Expected >0 :Struct nodes (Widget/Part/Holder), got {struct_count}"
            )
