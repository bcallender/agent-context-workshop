"""The edge contract that complements the parsers' Symbol (node) contract."""

from __future__ import annotations

from collections import OrderedDict

import pydantic.dataclasses
from pydantic import TypeAdapter

EDGE_TYPES = (
    "CONTAINS",
    "HAS_METHOD",
    "IMPLEMENTS",
    "REEXPORTS",
    "RETURNS",
    "TAKES",
    "HAS_FIELD",
    "CALLS",
    "REFERENCES",
)


@pydantic.dataclasses.dataclass
class Edge:
    src: str  # source node qualified_name (canonical)
    dst: str  # target node qualified_name (canonical)
    type: str  # one of EDGE_TYPES
    rung: str  # "resolution" | "calls"
    extractor: str  # "rustdoc-json" | "rust-analyzer-scip"
    files: list[str] | None = None  # per-site filepaths (parallel to lines)
    lines: list[int] | None = None
    count: int = 1
    synthetic: bool = False  # e.g. derive impls
    wrapper: str | None = None  # outer type when reached through a generic, e.g. "Result"
    position: str | None = None  # "return" | "param" | "field"


_ADAPTER = TypeAdapter(list[Edge])


def edge_rows(edges: list[Edge]) -> list[dict]:
    return _ADAPTER.dump_python(edges, mode="json")


def dedupe_edges(edges: list[Edge]) -> list[Edge]:
    out: OrderedDict[tuple, Edge] = OrderedDict()
    for e in edges:
        key = (e.src, e.dst, e.type, e.position)
        if key in out:
            cur = out[key]
            cur.files = (cur.files or []) + (e.files or [])
            cur.lines = (cur.lines or []) + (e.lines or [])
            cur.count += e.count
            cur.synthetic = cur.synthetic and e.synthetic
        else:
            out[key] = e
    return list(out.values())
