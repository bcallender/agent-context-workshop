"""End-to-end demo: rustdoc JSON -> graph -> Neo4j -> blast radius.

Usage::

    docker compose up -d
    NEO4J_TEST_URI=neo4j://localhost:7687 NEO4J_TEST_PASSWORD=workshop123 \\
        uv run python examples/blast_radius_demo.py \\
        tests/fixtures/rustdoc_edges.json edgecrate::Part
"""

import os
import sys

from context_workshop.graph.loader import connect, load
from context_workshop.graph.rust import build_rust_graph
from context_workshop.graph.tools import GraphTools


def main(json_path: str, target_qn: str) -> None:
    nodes, edges = build_rust_graph(json_path)
    with connect(
        os.environ["NEO4J_TEST_URI"],
        password=os.getenv("NEO4J_TEST_PASSWORD", "workshop123"),
    ) as drv:
        stats = load(drv, nodes, edges, reset=True)
        print(
            f"loaded {stats['nodes']} nodes, {stats['edges']} edges, {stats['isolated']} isolated"
        )
        for row in GraphTools(drv).blast_radius(target_qn, depth=3):
            print(
                f"  {row['qualified_name']}  "
                f"({row['filepath']}:{row['line_start']})  "
                f"via {'->'.join(row['path'])}"
            )


if __name__ == "__main__":
    if len(sys.argv) != 3:  # noqa: PLR2004
        print(f"Usage: {sys.argv[0]} <rustdoc_edges.json> <target_qualified_name>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
