"""Curated, pre-written-Cypher traversal tools over the code knowledge graph.

Each q_* function is a pure (cypher, params) builder (unit-testable without a
DB). GraphTools binds them to a driver. Results are citations only
(qualified_name + file:line), never node bodies, to keep agent tokens bounded.
"""

from __future__ import annotations

_RET = (
    "RETURN n.qualified_name AS qualified_name, n.filepath AS filepath, n.line_start AS line_start"
)


def q_get_symbol(qn: str):
    return (
        f"MATCH (n:Symbol {{qualified_name:$qn}}) {_RET}, n.docstring AS docstring",
        {"qn": qn},
    )


def q_search(term: str, limit: int = 10):
    # Tokenize so a descriptive phrase ("distance metric") matches a symbol whose name/qualified_name
    # contains EVERY word — not just an exact contiguous substring, which never matches a multi-word
    # phrase (qualified_names have no spaces). A single identifier behaves exactly as before. This makes
    # `search` forgiving like a keyword search instead of silently returning nothing on a phrase.
    tokens = [t for t in term.lower().split() if t]
    if not tokens:
        return (
            "MATCH (n:Symbol) WHERE false " + _RET + " LIMIT $limit",
            {"tokens": [], "limit": limit},
        )
    return (
        "MATCH (n:Symbol) WHERE ALL(t IN $tokens WHERE "
        "toLower(n.qualified_name) CONTAINS t OR toLower(coalesce(n.name,'')) CONTAINS t) "
        f"{_RET} LIMIT $limit",
        {"tokens": tokens, "limit": limit},
    )


def q_blast_radius(qn: str, depth: int = 3):
    d = max(1, min(int(depth), 5))
    return (
        f"MATCH (t:Symbol {{qualified_name:$qn}})"
        f"<-[r:CALLS|RETURNS|TAKES|HAS_FIELD|HAS_METHOD|IMPLEMENTS*1..{d}]-(n) "
        "RETURN DISTINCT n.qualified_name AS qualified_name, n.filepath AS filepath, "
        "n.line_start AS line_start, [rel IN r | type(rel)] AS path",
        {"qn": qn},
    )


def q_implementors(trait_qn: str):
    return (
        f"MATCH (n:Symbol)-[:IMPLEMENTS]->(:Symbol {{qualified_name:$qn}}) {_RET}",
        {"qn": trait_qn},
    )


def q_methods_of(type_qn: str):
    return (
        f"MATCH (:Symbol {{qualified_name:$qn}})-[:HAS_METHOD]->(n:Symbol) {_RET}",
        {"qn": type_qn},
    )


def q_public_api(crate: str):
    return (
        f"MATCH (n:Symbol:Public {{crate:$crate}}) {_RET} ORDER BY n.qualified_name",
        {"crate": crate},
    )


def q_neighborhood(qn: str, limit: int = 50):
    return (
        "MATCH (c:Symbol {qualified_name:$qn})-[r]-(n:Symbol) "
        "RETURN type(r) AS rel, startNode(r).qualified_name = $qn AS outgoing, "
        "n.qualified_name AS qualified_name, n.filepath AS filepath, n.line_start AS line_start "
        "LIMIT $limit",
        {"qn": qn, "limit": limit},
    )


class GraphTools:
    """Bind the q_* builders to a Neo4j driver."""

    def __init__(self, driver):
        self._driver = driver

    def _run(self, builder, *args, **kwargs) -> list[dict]:
        cypher, params = builder(*args, **kwargs)
        with self._driver.session() as s:
            return s.run(cypher, **params).data()

    def get_symbol(self, qualified_name: str) -> list[dict]:
        return self._run(q_get_symbol, qualified_name)

    def search(self, term: str, limit: int = 10) -> list[dict]:
        return self._run(q_search, term, limit)

    def blast_radius(self, qualified_name: str, depth: int = 3) -> list[dict]:
        return self._run(q_blast_radius, qualified_name, depth)

    def implementors(self, trait_qualified_name: str) -> list[dict]:
        return self._run(q_implementors, trait_qualified_name)

    def methods_of(self, type_qualified_name: str) -> list[dict]:
        return self._run(q_methods_of, type_qualified_name)

    def public_api(self, crate: str) -> list[dict]:
        return self._run(q_public_api, crate)

    def neighborhood(self, qualified_name: str, limit: int = 50) -> list[dict]:
        return self._run(q_neighborhood, qualified_name, limit)

    def callers(self, qualified_name: str) -> list[dict]:
        """Inbound CALLS — requires the SCIP deep layer (Tier C); empty until loaded."""
        cy = f"MATCH (n:Symbol)-[:CALLS]->(:Symbol {{qualified_name:$qn}}) {_RET}"
        with self._driver.session() as s:
            return s.run(cy, qn=qualified_name).data()

    def callees(self, qualified_name: str) -> list[dict]:
        """Outbound CALLS — requires the SCIP deep layer (Tier C); empty until loaded."""
        cy = f"MATCH (:Symbol {{qualified_name:$qn}})-[:CALLS]->(n:Symbol) {_RET}"
        with self._driver.session() as s:
            return s.run(cy, qn=qualified_name).data()
