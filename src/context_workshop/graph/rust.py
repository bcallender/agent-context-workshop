"""Build a Rust code knowledge graph (nodes + edges) from rustdoc JSON.

Consumes the Rung-1 Symbol rows from parsers.load_rust_rustdoc plus the raw
rustdoc JSON (for the module tree + signatures). The parsers package is not
modified; all graph-specific interpretation lives here.
"""

from __future__ import annotations

import logging

from context_workshop.graph.schema import Edge, dedupe_edges
from context_workshop.parsers import load_rust_rustdoc  # noqa: F401 (re-exported convenience)
from context_workshop.parsers.schema import Symbol, rows

logger = logging.getLogger(__name__)

_KIND_LABEL: dict[str, str] = {
    "module": "Module",
    "struct": "Struct",
    "enum": "Enum",
    "trait": "Trait",
    "type_alias": "TypeAlias",
    "function": "Function",
    "method": "Method",
    "const": "Const",
    "crate": "Crate",
}


def _kind_label(kind: str) -> str:
    """Map a lowercase kind property value to the Capitalized Neo4j label."""
    return _KIND_LABEL.get(kind, kind.title())


def _module_tree(data: dict) -> tuple[dict, dict]:
    """Return (child_id -> parent_id, module_id -> is_public) over index modules."""
    idx = data["index"]
    parent: dict[str, str] = {}
    module_public: dict[str, bool] = {}
    for mid, item in idx.items():
        inner = item.get("inner") or {}
        mod = inner.get("module") if isinstance(inner, dict) else None
        if not isinstance(mod, dict):
            continue
        module_public[mid] = item.get("visibility") == "public"
        for child in mod.get("items") or []:
            parent[str(child)] = mid
    return parent, module_public


def _effective_public_paths(data: dict) -> set[str]:
    idx = data["index"]
    paths = data["paths"]
    parent, module_public = _module_tree(data)

    def path_of(i: str) -> str | None:
        p = paths.get(str(i))
        return "::".join(p["path"]) if p else None

    def chain_public(i: str) -> bool:
        cur = parent.get(str(i))
        while cur is not None:
            # ancestors that are modules must themselves be public
            if cur in module_public and not module_public[cur]:
                return False
            cur = parent.get(cur)
        return True

    out: set[str] = set()
    for iid, item in idx.items():
        if item.get("visibility") != "public":
            continue
        if not chain_public(iid):
            continue
        p = path_of(iid)
        if p:
            out.add(p)
    return out


def prepare_nodes(symbols: list[Symbol], data: dict) -> list[dict]:
    eff = _effective_public_paths(data)
    canonical: dict[str, dict] = {}
    exported: dict[str, list[str]] = {}

    for sym, row in zip(symbols, rows(symbols), strict=True):
        if sym.is_reexport:
            exported.setdefault(sym.canonical_path, []).append(sym.exported_path)
            continue
        qn = sym.qualified_name
        node = {
            k: v
            for k, v in row.items()
            if k not in ("is_reexport", "exported_path", "canonical_path")
        }
        node["crate"] = qn.split("::", 1)[0]
        node["effective_public"] = sym.canonical_path in eff
        node["exported_paths"] = []
        node["kind_label"] = _kind_label(node.get("kind") or "")
        canonical[qn] = node

    for canon_path, paths_list in exported.items():
        if canon_path in canonical:
            canonical[canon_path]["exported_paths"] = sorted(set(paths_list))
            canonical[canon_path]["effective_public"] = True  # re-exported ⇒ public surface

    return list(canonical.values())


def _accessors(data: dict):
    idx, paths = data["index"], data["paths"]

    def path_of(i: object) -> str | None:
        p = paths.get(str(i))
        return "::".join(p["path"]) if p else None

    def type_path(t: object) -> str | None:
        if not isinstance(t, dict):
            return None
        if "resolved_path" in t:
            r = t["resolved_path"]
            if not isinstance(r, dict):
                return None
            rid = r.get("id")
            return (path_of(rid) if rid is not None else None) or r.get("path")
        if "qualified_path" in t:
            q = t["qualified_path"]
            return type_path(q.get("self_type")) if isinstance(q, dict) else None
        return None

    def span(i: object) -> tuple[str | None, int | None]:
        s = (idx.get(str(i)) or {}).get("span")
        return (s["filename"], s["begin"][0]) if s else (None, None)

    return idx, path_of, type_path, span


def _tier_a_edges(data: dict) -> list[Edge]:
    idx, path_of, type_path, span = _accessors(data)
    edges: list[Edge] = []

    # CONTAINS: every module -> each genuine structural child (skip `use` re-export items).
    # REEXPORTS: emitted here too, from the owning module, not the crate root.
    for mid, item in idx.items():
        inner = item.get("inner") or {}
        mod = inner.get("module") if isinstance(inner, dict) else None
        if not isinstance(mod, dict):
            continue
        msrc = path_of(mid) or item.get("name")
        if msrc is None:
            continue
        for child in mod.get("items") or []:
            child_item = idx.get(str(child)) or {}
            child_inner = child_item.get("inner") or {}
            # Skip `use` items for CONTAINS — they are re-export aliases, not structural members.
            if "use" in (child_inner if isinstance(child_inner, dict) else {}):
                use = child_inner["use"]
                if isinstance(use, dict):
                    tgt = use.get("id")
                    canon = path_of(tgt) if tgt is not None else None
                    if canon:
                        edges.append(
                            Edge(
                                src=msrc,
                                dst=canon,
                                type="REEXPORTS",
                                rung="resolution",
                                extractor="rustdoc-json",
                            )
                        )
                continue
            dst = path_of(child)
            if dst:
                edges.append(
                    Edge(
                        src=msrc,
                        dst=dst,
                        type="CONTAINS",
                        rung="resolution",
                        extractor="rustdoc-json",
                    )
                )

    # HAS_METHOD + IMPLEMENTS from impl blocks.
    for item in idx.values():
        inner = item.get("inner") or {}
        impl = inner.get("impl") if isinstance(inner, dict) else None
        if not isinstance(impl, dict):
            continue
        parent = type_path(impl.get("for"))
        if parent is None:
            continue
        synthetic = bool(impl.get("synthetic")) or impl.get("blanket_impl") is not None
        trait = impl.get("trait")
        if isinstance(trait, dict):
            tdst = (path_of(trait.get("id")) if trait.get("id") is not None else None) or trait.get(
                "path"
            )
            if tdst:
                edges.append(
                    Edge(
                        src=parent,
                        dst=tdst,
                        type="IMPLEMENTS",
                        rung="resolution",
                        extractor="rustdoc-json",
                        synthetic=synthetic,
                    )
                )
        for item_id in impl.get("items") or []:
            mi = idx.get(str(item_id)) or {}
            minner = mi.get("inner") or {}
            if not (isinstance(minner, dict) and "function" in minner):
                continue
            name = mi.get("name")
            if not name:
                continue
            mdst = path_of(item_id) or f"{parent}::{name}"
            f, ln = span(item_id)
            edges.append(
                Edge(
                    src=parent,
                    dst=mdst,
                    type="HAS_METHOD",
                    rung="resolution",
                    extractor="rustdoc-json",
                    files=[f] if f else None,
                    lines=[ln] if ln else None,
                )
            )

    return edges


def _named_types(
    t: object, type_path, *, wrapper: str | None = None, dropped: list | None = None
) -> list[tuple[str, str | None]]:
    """All named, resolvable types in a rustdoc Type, recursing into generic args.

    Returns a list of (canonical_path, wrapper) pairs.  ``wrapper`` is the name
    of the enclosing generic type (e.g. ``"Option"``), or ``None`` for the outermost.
    Primitives, generic params, ``impl Trait``, and unresolvable refs are omitted
    (and optionally counted via ``dropped``).
    """
    if not isinstance(t, dict):
        return []
    found: list[tuple[str, str | None]] = []
    outer = type_path(t)
    if "resolved_path" in t and isinstance(t["resolved_path"], dict):
        if outer:
            found.append((outer, wrapper))
        else:
            if dropped is not None:
                dropped.append(repr(t.get("resolved_path", {}).get("path")))
        args = t["resolved_path"].get("args") or {}
        ab = args.get("angle_bracketed") if isinstance(args, dict) else None
        # wrapper label for inner types = short name of the enclosing type
        inner_wrapper = (outer.rsplit("::", 1)[-1] if outer else None) or wrapper
        for a in (ab or {}).get("args", []) if isinstance(ab, dict) else []:
            if isinstance(a, dict) and isinstance(a.get("type"), dict):
                found += _named_types(a["type"], type_path, wrapper=inner_wrapper, dropped=dropped)
    else:
        if dropped is not None:
            dropped.append("unresolvable")  # &T, impl Trait, primitive, generic param
    return found


def _tier_b_edges(data: dict, dropped: list | None = None) -> list[Edge]:
    idx, path_of, type_path, span = _accessors(data)
    edges: list[Edge] = []

    # Build method-id -> canonical so RETURNS/TAKES use the Type::method key.
    method_canon: dict[str, str] = {}
    for item in idx.values():
        inner = item.get("inner") or {}
        impl = inner.get("impl") if isinstance(inner, dict) else None
        if not isinstance(impl, dict):
            continue
        parent = type_path(impl.get("for"))
        for item_id in impl.get("items") or []:
            mi = idx.get(str(item_id)) or {}
            mi_inner = mi.get("inner") or {}
            if isinstance(mi_inner, dict) and "function" in mi_inner:
                nm = mi.get("name")
                if parent and nm:
                    method_canon[str(item_id)] = path_of(item_id) or f"{parent}::{nm}"

    for iid, item in idx.items():
        inner = item.get("inner") or {}
        if not isinstance(inner, dict):
            continue
        if "function" in inner:
            src = method_canon.get(iid) or path_of(iid)
            if src is None:
                continue
            sig = (inner["function"] or {}).get("sig") or {}
            f, ln = span(iid)
            out = sig.get("output")
            if out is not None:
                for dst, wrap in _named_types(out, type_path, dropped=dropped):
                    edges.append(
                        Edge(
                            src=src,
                            dst=dst,
                            type="RETURNS",
                            rung="resolution",
                            extractor="rustdoc-json",
                            position="return",
                            wrapper=wrap,
                            files=[f] if f else None,
                            lines=[ln] if ln else None,
                        )
                    )
            for _name, ty in sig.get("inputs") or []:
                for dst, wrap in _named_types(ty, type_path, dropped=dropped):
                    edges.append(
                        Edge(
                            src=src,
                            dst=dst,
                            type="TAKES",
                            rung="resolution",
                            extractor="rustdoc-json",
                            position="param",
                            wrapper=wrap,
                        )
                    )
        elif "struct" in inner:
            src = path_of(iid)
            kind = (inner["struct"] or {}).get("kind") or {}
            fields = (kind.get("plain") or {}).get("fields") if isinstance(kind, dict) else None
            for fid in fields or []:
                fitem = idx.get(str(fid)) or {}
                fty = (fitem.get("inner") or {}).get("struct_field")
                if fty is not None:
                    for dst, wrap in _named_types(fty, type_path, dropped=dropped):
                        if src:
                            edges.append(
                                Edge(
                                    src=src,
                                    dst=dst,
                                    type="HAS_FIELD",
                                    rung="resolution",
                                    extractor="rustdoc-json",
                                    position="field",
                                    wrapper=wrap,
                                )
                            )
    return edges


def extract_edges(symbols: list[Symbol], data: dict, *, dropped: list | None = None) -> list[Edge]:
    return dedupe_edges(_tier_a_edges(data) + _tier_b_edges(data, dropped=dropped))


def _synthesize_crate_root(data: dict, existing_nodes: list[dict]) -> list[dict]:
    """Synthesize a crate-root :Symbol node if one is not already present.

    ``load_rust_rustdoc`` skips the crate-root module because it has no ``paths`` entry.
    Without it, CONTAINS/REEXPORTS edges whose ``src`` is the crate name silently fail to
    match — those edges are simply dropped by the MATCH clause.  We produce a minimal
    Symbol-shaped node dict so those edges resolve correctly.
    """
    idx = data["index"]
    root_id = str(data.get("root", "0"))
    root_item = idx.get(root_id) or {}
    crate_name: str | None = root_item.get("name") or None
    if not crate_name:
        raise ValueError("rustdoc root has no resolvable crate name")

    existing_qns = {n["qualified_name"] for n in existing_nodes}
    if crate_name in existing_qns:
        return existing_nodes  # already present — nothing to do

    root_node: dict = {
        "qualified_name": crate_name,
        "name": crate_name,
        "kind": "crate",  # lowercase — consistent with all other nodes
        "kind_label": _kind_label("crate"),  # "Crate" — used by SET n:$(r.kind_label)
        "language": "rust",
        "extractor": "rustdoc-json",
        "rung": "resolution",
        "crate": crate_name,
        "effective_public": True,
        "exported_paths": [],
        # Remaining Symbol-shape fields default to None
        "filepath": None,
        "line_start": None,
        "line_end": None,
        "docstring": None,
        "signature": None,
        "visibility": "public",
        "is_public": True,
        "parent": None,
        "parameters": None,
        "bases": None,
        "cfg_gated": None,
    }
    return [root_node, *existing_nodes]


def build_rust_graph(json_path, *, allow_version_mismatch: bool = False):
    import json as _json
    from pathlib import Path as _Path

    symbols = load_rust_rustdoc(json_path, allow_version_mismatch=allow_version_mismatch)
    data = _json.loads(_Path(json_path).read_text())
    nodes = prepare_nodes(symbols, data)
    nodes = _synthesize_crate_root(data, nodes)
    dropped: list[str] = []
    edges = extract_edges(symbols, data, dropped=dropped)
    if dropped:
        logger.info("dropped %d unresolvable type edges", len(dropped))
    return nodes, edges
