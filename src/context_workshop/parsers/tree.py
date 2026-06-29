"""Small hierarchy helpers for Symbol rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def build_tree(rows: Iterable[Mapping[str, Any]] | Mapping[str, list[Any]]) -> dict[str, Any]:
    """Build a nested tree from flat Symbol row dicts."""
    tree: dict[str, Any] = {"name": "root", "kind": "root", "children": {}}
    for row in _iter_rows(rows):
        qualified_name = row["qualified_name"]
        path_parts = row.get("path_parts") or _path_parts(row)
        current = tree
        for part in path_parts[:-1]:
            current = _upsert_child(current, part, name=part, kind="unknown")
        if path_parts:
            _upsert_child(
                current,
                path_parts[-1],
                name=row["name"],
                kind=row.get("kind", row.get("type")),
                qualified_name=qualified_name,
            )
    return tree


def tree_to_string(node: dict[str, Any], *, indent: int = 0, max_depth: int = 3) -> str:
    """Render a compact text view of a hierarchy tree."""
    if indent > max_depth:
        return ""
    result = ""
    if indent > 0:
        result += "  " * (indent - 1) + f"├─ [{_node_kind(node)}] {node['name']}\n"
    children = sorted(
        node.get("children", {}).values(),
        key=lambda child: (
            {"module": 0, "class": 1, "function": 2, "method": 3}.get(_node_kind(child), 4),
            child["name"],
        ),
    )
    for child in children[:10]:
        result += tree_to_string(child, indent=indent + 1, max_depth=max_depth)
    if len(children) > 10:
        result += "  " * indent + f"... and {len(children) - 10} more\n"
    return result


def _iter_rows(
    rows: Iterable[Mapping[str, Any]] | Mapping[str, list[Any]],
) -> Iterable[Mapping[str, Any]]:
    """Yield row dicts from public list-of-dicts rows or legacy column dicts."""
    if isinstance(rows, Mapping):
        row_count = len(rows["qualified_name"])
        for i in range(row_count):
            yield {key: values[i] for key, values in rows.items()}
        return

    yield from rows


def _path_parts(row: Mapping[str, Any]) -> list[str]:
    separator = "::" if row.get("language") == "rust" else "."
    return [part for part in row["qualified_name"].split(separator) if part]


def _upsert_child(
    parent: dict[str, Any],
    key: str,
    *,
    name: str,
    kind: str | None,
    qualified_name: str | None = None,
) -> dict[str, Any]:
    children = parent.setdefault("children", {})
    child = children.setdefault(key, {"name": name, "kind": kind or "unknown", "children": {}})
    child["name"] = name
    child["kind"] = kind or "unknown"
    if qualified_name is not None:
        child["qualified_name"] = qualified_name
    child.setdefault("children", {})
    return child


def _node_kind(node: Mapping[str, Any]) -> str:
    return node.get("kind", node.get("type", "unknown"))
