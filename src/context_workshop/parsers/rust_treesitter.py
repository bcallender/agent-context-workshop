"""Syntactic Rust symbol extraction via tree-sitter (Rung 0).

Canonical py-tree-sitter API: tree_sitter + the official tree-sitter-rust grammar.
Deliberately syntactic: it sees tokens, never resolves names/types/re-exports.
Symbols carry provenance fields so the depth boundary is explicit in the data.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter as ts
import tree_sitter_rust

from context_workshop.parsers.schema import Symbol

PARSER = ts.Parser(ts.Language(tree_sitter_rust.language()))

ITEM_KIND = {
    "function_item": "function",
    "struct_item": "struct",
    "enum_item": "enum",
    "trait_item": "trait",
    "mod_item": "module",
    "const_item": "const",
    "static_item": "static",
    "type_item": "type_alias",
    "union_item": "union",
    "macro_definition": "macro",
}


def text(node) -> str:
    return node.text.decode("utf8", "replace") if node is not None else ""


def module_path_for(path: Path, root: Path) -> tuple[str, list[str]]:
    """Infer (crate, [module segments]) from a file path (Rust file=module convention)."""
    parts = list(path.relative_to(root).parts)
    crate = root.name
    if "src" in parts:
        i = parts.index("src")
        if i > 0:
            crate = parts[i - 1]
        tail = parts[i + 1 :]
    else:
        tail = parts
    segs = []
    for seg in tail:
        seg = seg[:-3] if seg.endswith(".rs") else seg
        if seg in ("lib", "main", "mod"):
            continue
        segs.append(seg)
    return crate, segs


def doc_and_attrs(node) -> tuple[str | None, bool]:
    """Walk preceding siblings: collect /// doc lines, detect a #[cfg(...)] gate."""
    docs: list[str] = []
    cfg = False
    sib = node.prev_sibling
    while sib is not None:
        if sib.type in ("line_comment", "block_comment"):
            t = text(sib)
            if t.startswith("///") or t.startswith("//!") or t.startswith("/**"):
                docs.append(t.lstrip("/!*").strip())
            else:
                break
        elif sib.type == "attribute_item":
            if "cfg(" in text(sib):
                cfg = True
        else:
            break
        sib = sib.prev_sibling
    docs.reverse()
    return ("\n".join(docs) or None), cfg


def visibility(node) -> str | None:
    for c in node.children:
        if c.type == "visibility_modifier":
            return text(c)
    return None


def signature(fn) -> str:
    name = text(fn.child_by_field_name("name"))
    params = text(fn.child_by_field_name("parameters"))
    ret = fn.child_by_field_name("return_type")
    return f"{name}{params}" + (f" -> {text(ret)}" if ret is not None else "")


def _final_name(node) -> str | None:
    if node.type in ("identifier", "type_identifier"):
        return text(node)
    if node.type == "use_as_clause":
        alias = node.child_by_field_name("alias")
        return text(alias) if alias else None
    if node.type == "scoped_identifier":
        nm = node.child_by_field_name("name")
        return text(nm) if nm else None
    return None


def reexport_names(use_node) -> list[str]:
    """The final identifiers brought into scope by a `pub use` (brace-list aware)."""
    names: list[str] = []
    lists = [n for n in _walk(use_node) if n.type == "use_list"]
    if lists:
        for lst in lists:
            for m in lst.named_children:
                nm = _final_name(m)
                if nm:
                    names.append(nm)
    else:
        args = [c for c in use_node.named_children if c.type != "visibility_modifier"]
        if args:
            nm = _final_name(args[-1])
            if nm:
                names.append(nm)
    return names


def _walk(node):
    yield node
    for c in node.named_children:
        yield from _walk(c)


def _make_symbol(
    kind: str,
    name: str,
    crate: str,
    segs: list[str],
    node,
    filepath: str,
    *,
    impl_type: str | None = None,
    is_reexport: bool = False,
    exported_path: str | None = None,
    sig: str | None = None,
) -> Symbol:
    qn_parts = [crate, *segs] + ([impl_type] if impl_type else []) + ([name] if name else [])
    doc, cfg = doc_and_attrs(node)
    vis = visibility(node)
    return Symbol(
        language="rust",
        extractor="tree-sitter",
        rung="syntactic",
        kind=kind,
        name=name,
        qualified_name="::".join(qn_parts),
        filepath=filepath,
        line_start=node.start_point.row + 1,
        line_end=node.end_point.row + 1,
        docstring=doc,
        signature=sig,
        visibility=vis,
        is_public=vis == "pub",
        parent=impl_type,
        is_reexport=is_reexport,
        exported_path=exported_path,
        canonical_path=None,
        parameters=None,
        bases=None,
        cfg_gated=cfg,
    )


def visit(
    node, crate: str, segs: list[str], impl_type: str | None, rows: list[Symbol], filepath: str
) -> None:
    for child in node.named_children:
        t = child.type
        if t == "mod_item":
            name = text(child.child_by_field_name("name"))
            rows.append(_make_symbol("module", name, crate, segs, child, filepath))
            body = child.child_by_field_name("body")
            if body is not None:
                visit(body, crate, segs + [name], None, rows, filepath)
        elif t == "impl_item":
            self_t = text(child.child_by_field_name("type"))
            body = child.child_by_field_name("body")
            if body is not None:
                visit(body, crate, segs, self_t, rows, filepath)
        elif t == "trait_item":
            name = text(child.child_by_field_name("name"))
            rows.append(_make_symbol("trait", name, crate, segs, child, filepath))
            body = child.child_by_field_name("body")
            if body is not None:
                visit(body, crate, segs, name, rows, filepath)
        elif t == "function_item":
            name = text(child.child_by_field_name("name"))
            kind = "method" if impl_type else "function"
            rows.append(
                _make_symbol(
                    kind,
                    name,
                    crate,
                    segs,
                    child,
                    filepath,
                    impl_type=impl_type,
                    sig=signature(child),
                )
            )
        elif t in ITEM_KIND:
            name = text(child.child_by_field_name("name"))
            rows.append(
                _make_symbol(ITEM_KIND[t], name, crate, segs, child, filepath, impl_type=impl_type)
            )
        elif t == "use_declaration" and visibility(child) == "pub":
            for nm in reexport_names(child):
                rows.append(
                    _make_symbol(
                        "reexport",
                        nm,
                        crate,
                        segs,
                        child,
                        filepath,
                        is_reexport=True,
                        exported_path="::".join([crate, *segs, nm]),
                        sig=text(child),
                    )
                )


def extract_rust_source(
    source: bytes,
    *,
    filepath: str,
    crate: str,
    module_segs: list[str],
) -> list[Symbol]:
    """Parse Rust source bytes and return Symbol objects for all discovered items."""
    tree = PARSER.parse(source)
    result: list[Symbol] = []
    visit(tree.root_node, crate, module_segs, None, result, filepath)
    return result


def extract_rust_crate(crate_dir: str | Path) -> list[Symbol]:
    """Walk all *.rs files in crate_dir (skipping /target/) and extract symbols."""
    root = Path(crate_dir).resolve()
    files = [p for p in root.rglob("*.rs") if "/target/" not in str(p)]
    result: list[Symbol] = []
    for f in files:
        crate, segs = module_path_for(f, root)
        result.extend(
            extract_rust_source(f.read_bytes(), filepath=str(f), crate=crate, module_segs=segs)
        )
    return result
