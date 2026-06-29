"""The unified symbol contract every parser emits.

One Pydantic dataclass is the source of truth. Parsers stay fenic-free; only
``fenic_schema`` imports fenic, lazily, so the canonical table can be created
with a forced (explicit) schema rather than relying on inference.
"""

from __future__ import annotations

from typing import Literal

import pydantic.dataclasses
from pydantic import TypeAdapter


@pydantic.dataclasses.dataclass
class Symbol:
    # identity
    language: str
    kind: str
    name: str
    qualified_name: str
    extractor: Literal["griffe", "tree-sitter", "rustdoc-json"]
    rung: Literal["syntactic", "resolution"]
    # location (citation evidence)
    filepath: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    # description
    docstring: str | None = None
    signature: str | None = None
    visibility: str | None = None
    is_public: bool = False
    parent: str | None = None
    # resolution (rung-aware)
    is_reexport: bool = False
    exported_path: str | None = None
    canonical_path: str | None = None
    # language-specific extras ([] = empty instance, None = N/A for language)
    parameters: list[str] | None = None
    bases: list[str] | None = None
    cfg_gated: bool | None = None


_ADAPTER = TypeAdapter(list[Symbol])


def rows(symbols: list[Symbol]) -> list[dict]:
    """Plain JSON-able dicts for Fenic/DuckDB ingestion (Pydantic-controlled)."""
    return _ADAPTER.dump_python(symbols, mode="json")


# Single source of column order+type for the contract. Each tag projects to both
# a pyarrow type (ingestion / forced typing) and a fenic type (catalog persistence).
_FIELDS = [
    ("language", "str"),
    ("kind", "str"),
    ("name", "str"),
    ("qualified_name", "str"),
    ("extractor", "str"),
    ("rung", "str"),
    ("filepath", "str"),
    ("line_start", "int"),
    ("line_end", "int"),
    ("docstring", "str"),
    ("signature", "str"),
    ("visibility", "str"),
    ("is_public", "bool"),
    ("parent", "str"),
    ("is_reexport", "bool"),
    ("exported_path", "str"),
    ("canonical_path", "str"),
    ("parameters", "list"),
    ("bases", "list"),
    ("cfg_gated", "bool"),
]


def arrow_schema():
    """pyarrow schema for the Symbol contract — the FORCED ingestion schema.

    fenic 0.10.0's create_dataframe() has no schema= param; types are carried by
    the input container. A typed pyarrow Table forces correct types even when a
    column is all-None / all-empty-list (raw list[dict] raises on a Null dtype).
    """
    import pyarrow as pa

    m = {"str": pa.string(), "int": pa.int64(), "bool": pa.bool_(), "list": pa.list_(pa.string())}
    return pa.schema([(n, m[t]) for n, t in _FIELDS])


def to_arrow(symbols: list[Symbol]):
    """Forced-schema pyarrow Table ready for session.create_dataframe()."""
    import pyarrow as pa

    return pa.Table.from_pylist(rows(symbols), schema=arrow_schema())


def fenic_schema():
    """Equivalent Fenic Schema, for persisting via session.catalog.create_table()."""
    import fenic as fc

    m = {
        "str": fc.StringType,
        "int": fc.IntegerType,
        "bool": fc.BooleanType,
        "list": fc.ArrayType(fc.StringType),
    }
    return fc.Schema([fc.ColumnField(n, m[t]) for n, t in _FIELDS])
