"""Thin Neo4j loader: pure Cypher/param builders + a driver-driven `load`.

No fenic. Relationship TYPE cannot be parameterized in Cypher, so edges are
grouped by type and the (validated) type name is interpolated into the query.

Dynamic labels use native Cypher 5 ``SET n:$(r.kind_label)`` syntax — no APOC required.
"""

from __future__ import annotations

from collections.abc import Iterator

from context_workshop.graph.schema import EDGE_TYPES, Edge, edge_rows

CONSTRAINT_CYPHER = (
    "CREATE CONSTRAINT sym_qn IF NOT EXISTS FOR (n:Symbol) REQUIRE n.qualified_name IS UNIQUE"
)
RESET_CYPHER = "MATCH (n) DETACH DELETE n"
ISOLATED_NODES_CYPHER = "MATCH (n:Symbol) WHERE NOT (n)--() RETURN count(n) AS n"

# Native Cypher 5 dynamic labels — SET n:$(expr) requires Neo4j 5.26+ (shipped in neo4j:5).
# No APOC dependency.
NODE_MERGE_CYPHER = """
UNWIND $rows AS r
MERGE (n:Symbol {qualified_name: r.qualified_name})
SET n += r
WITH n, r WHERE r.kind_label IS NOT NULL
SET n:$(r.kind_label)
WITH n, r WHERE r.effective_public = true
SET n:Public
""".strip()


def node_batches(nodes: list[dict], size: int = 1000) -> Iterator[list[dict]]:
    for i in range(0, len(nodes), size):
        yield nodes[i : i + size]


def edge_groups(edges: list[Edge]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for e, row in zip(edges, edge_rows(edges), strict=True):
        props = {k: v for k, v in row.items() if k not in ("src", "dst", "type") and v is not None}
        groups.setdefault(e.type, []).append({"src": e.src, "dst": e.dst, "props": props})
    return groups


def edge_merge_cypher(edge_type: str) -> str:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"unknown edge type {edge_type!r}")
    return f"""
UNWIND $rows AS r
MATCH (a:Symbol {{qualified_name: r.src}})
MATCH (b:Symbol {{qualified_name: r.dst}})
MERGE (a)-[e:{edge_type}]->(b)
SET e += r.props
""".strip()


def connect(uri: str, user: str = "neo4j", password: str = "workshop123"):
    """Return a Neo4j driver. Use as a context manager: ``with connect(...) as drv:``."""
    from neo4j import GraphDatabase

    return GraphDatabase.driver(uri, auth=(user, password))


def load(
    driver,
    nodes: list[dict],
    edges: list[Edge],
    *,
    reset: bool = True,
    assert_connected: bool = True,
) -> dict:
    """Merge *nodes* and *edges* into Neo4j; return ``{"nodes", "edges", "isolated"}`` stats.

    Raises ``RuntimeError`` when *assert_connected* is True and any Symbol node is isolated
    (i.e. has no relationships — indicates a qualified_name mismatch between nodes and edges).
    """
    with driver.session() as s:
        s.run(CONSTRAINT_CYPHER)
        if reset:
            s.run(RESET_CYPHER)
        for batch in node_batches(nodes):
            s.run(NODE_MERGE_CYPHER, rows=batch)
        for etype, rows in edge_groups(edges).items():
            cy = edge_merge_cypher(etype)
            for i in range(0, len(rows), 1000):
                s.run(cy, rows=rows[i : i + 1000])
        isolated = s.run(ISOLATED_NODES_CYPHER).single()["n"]
    if assert_connected and isolated:
        raise RuntimeError(
            f"{isolated} isolated nodes after load — qualified_name key mismatch "
            f"between nodes and edge src/dst (see normalization contract)"
        )
    return {"nodes": len(nodes), "edges": len(edges), "isolated": isolated}
