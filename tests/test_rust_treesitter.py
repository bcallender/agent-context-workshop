from context_workshop.parsers.rust_treesitter import extract_rust_source

SRC = b"""\
/// A widget.
pub struct Widget;

#[cfg(test)]
pub fn only_in_tests() {}

pub use inner::Thing;
"""


def _syms():
    return extract_rust_source(SRC, filepath="src/lib.rs", crate="demo", module_segs=[])


def test_struct_extracted_with_doc_and_visibility():
    s = [x for x in _syms() if x.kind == "struct" and x.name == "Widget"][0]
    assert s.language == "rust" and s.extractor == "tree-sitter" and s.rung == "syntactic"
    assert s.is_public is True and s.docstring == "A widget."


def test_cfg_gated_flagged():
    fn = [x for x in _syms() if x.name == "only_in_tests"][0]
    assert fn.cfg_gated is True


def test_pub_use_is_unresolved_reexport():
    rx = [x for x in _syms() if x.is_reexport and x.name == "Thing"][0]
    assert rx.exported_path == "demo::Thing"
    assert rx.canonical_path is None  # syntactic: cannot resolve
