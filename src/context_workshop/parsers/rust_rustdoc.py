"""Rung-1 (semantic) Rust extraction from rustdoc JSON.

Parses a pre-generated rustdoc JSON file (does NOT shell out to cargo).
``pub use`` re-exports are resolved to their canonical definition (path +
file:line); other public items emit their path from the ``paths`` table.

Format version targeted: 57 (nightly 1.96.0 2026-03-18).
"""

from __future__ import annotations

import json
from pathlib import Path

from context_workshop.parsers.schema import Symbol

SUPPORTED_FORMAT_VERSION = 57

KIND = {
    "function": "function",
    "struct": "struct",
    "trait": "trait",
    "enum": "enum",
    "type_alias": "type_alias",
    "constant": "const",
    "module": "module",
    "use": "reexport",
}


def _vis_str(v: object) -> str:
    return v if isinstance(v, str) else "restricted"


def _short_type_name(path: str) -> str:
    return path.rsplit("::", 1)[-1]


def load_rust_rustdoc(
    json_path: str | Path,
    *,
    allow_version_mismatch: bool = False,
) -> list[Symbol]:
    """Parse a rustdoc JSON file and return a list of :class:`Symbol` objects.

    Parameters
    ----------
    json_path:
        Path to the rustdoc JSON file produced by ``cargo rustdoc … --output-format json``.
    allow_version_mismatch:
        When *False* (default), raises :exc:`ValueError` if ``format_version``
        differs from :data:`SUPPORTED_FORMAT_VERSION`.  Set to *True* to
        proceed anyway (useful for exploratory work against a newer nightly).
    """
    data = json.loads(Path(json_path).read_text())

    fv = data.get("format_version")
    if fv != SUPPORTED_FORMAT_VERSION and not allow_version_mismatch:
        raise ValueError(
            f"unsupported rustdoc format_version={fv}; expected {SUPPORTED_FORMAT_VERSION}"
        )

    idx: dict = data["index"]
    paths: dict = data["paths"]

    def I(i: object) -> dict | None:  # noqa: E743 (intentional short name from probe)
        return idx.get(str(i))

    def P(i: object) -> dict | None:
        return paths.get(str(i))

    def path_of(i: object) -> str | None:
        p = P(i)
        return "::".join(p["path"]) if p else None

    def type_path(t: object) -> str | None:
        if not isinstance(t, dict):
            return None
        if "resolved_path" in t:
            resolved = t["resolved_path"]
            if not isinstance(resolved, dict):
                return None
            resolved_id = resolved.get("id")
            path = path_of(resolved_id) if resolved_id is not None else None
            return path or resolved.get("path")
        if "qualified_path" in t:
            qualified = t["qualified_path"]
            if not isinstance(qualified, dict):
                return None
            return type_path(qualified.get("self_type"))
        return None

    def span_loc(item: dict | None) -> tuple[str | None, int | None, int | None]:
        s = (item or {}).get("span")
        return (s["filename"], s["begin"][0], s["end"][0]) if s else (None, None, None)

    # Public path of the crate root module, used to build re-export exported_paths.
    root_path = path_of(data["root"]) or (I(data["root"]) or {}).get("name")
    if root_path is None:
        raise ValueError("rustdoc JSON has no resolvable crate root path")

    impls: list[tuple[str, str, list[object]]] = []
    associated_ids: set[str] = set()
    for it in idx.values():
        inner = it.get("inner") or {}
        if not isinstance(inner, dict) or "impl" not in inner:
            continue
        impl = inner["impl"]
        if not isinstance(impl, dict):
            continue
        if impl.get("blanket_impl") is not None or impl.get("synthetic"):
            continue
        parent_path = type_path(impl.get("for"))
        if parent_path is None:
            continue
        items = impl.get("items") or []
        impls.append((parent_path, _short_type_name(parent_path), items))
        associated_ids.update(str(item_id) for item_id in items)

    result: list[Symbol] = []
    for iid, it in idx.items():
        if iid in associated_ids:
            continue
        inner = it.get("inner") or {}
        if not isinstance(inner, dict) or not inner:
            continue
        tag = next(iter(inner))
        if tag not in KIND:
            continue  # skip impl / struct_field / assoc_* etc.

        fname, l0, l1 = span_loc(it)
        vis = it.get("visibility")

        if tag == "use":
            u = inner["use"]
            tgt = u.get("id")
            if tgt is None:
                continue  # glob re-export (id: null); skip unresolved
            canon = path_of(tgt)
            if canon is None:
                continue  # target has no paths entry; skip unresolved
            t_fname, t_l0, t_l1 = span_loc(I(tgt))
            name = u.get("name")
            exported = f"{root_path}::{name}"
            result.append(
                Symbol(
                    language="rust",
                    kind=KIND[tag],
                    name=name,
                    qualified_name=exported,
                    extractor="rustdoc-json",
                    rung="resolution",
                    filepath=t_fname,
                    line_start=t_l0,
                    line_end=t_l1,
                    docstring=it.get("docs"),
                    visibility=_vis_str(vis),
                    is_public=(vis == "public"),
                    is_reexport=True,
                    exported_path=exported,
                    canonical_path=canon,
                    parameters=None,
                    bases=None,
                    cfg_gated=None,
                )
            )
        else:
            canon = path_of(iid)
            if canon is None:
                continue  # no path entry (e.g. crate root); skip
            result.append(
                Symbol(
                    language="rust",
                    kind=KIND[tag],
                    name=it.get("name"),
                    qualified_name=canon,
                    extractor="rustdoc-json",
                    rung="resolution",
                    filepath=fname,
                    line_start=l0,
                    line_end=l1,
                    docstring=it.get("docs"),
                    visibility=_vis_str(vis),
                    is_public=(vis == "public"),
                    is_reexport=False,
                    exported_path=canon,
                    canonical_path=canon,
                    parameters=None,
                    bases=None,
                    cfg_gated=None,
                )
            )

    for parent_path, parent, items in impls:
        for item_id in items:
            it = I(item_id)
            inner = (it or {}).get("inner") or {}
            if not isinstance(inner, dict) or "function" not in inner:
                continue
            fname, l0, l1 = span_loc(it)
            vis = (it or {}).get("visibility")
            name = (it or {}).get("name")
            if name is None:
                continue
            canon = path_of(item_id) or f"{parent_path}::{name}"
            result.append(
                Symbol(
                    language="rust",
                    kind="method",
                    name=name,
                    qualified_name=canon,
                    extractor="rustdoc-json",
                    rung="resolution",
                    filepath=fname,
                    line_start=l0,
                    line_end=l1,
                    docstring=(it or {}).get("docs"),
                    visibility=_vis_str(vis),
                    is_public=(vis == "public"),
                    parent=parent,
                    is_reexport=False,
                    exported_path=canon,
                    canonical_path=canon,
                    parameters=None,
                    bases=None,
                    cfg_gated=None,
                )
            )

    return result
