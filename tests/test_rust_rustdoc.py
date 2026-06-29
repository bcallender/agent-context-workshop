import json
from pathlib import Path

import pytest

from context_workshop.parsers.rust_rustdoc import load_rust_rustdoc

# Fixture provenance: hand-trimmed rustdoc JSON, format_version=57
# (matches nightly 1.96.0 2026-03-18). Regenerate via:
#   PATH="$HOME/.rustup/toolchains/nightly-*/bin:$PATH" cargo rustdoc \
#     --manifest-path <crate>/Cargo.toml -- -Z unstable-options --output-format json
FIX = Path(__file__).parent / "fixtures" / "rustdoc_min.json"


def test_reexport_resolves_to_canonical_def():
    syms = load_rust_rustdoc(FIX)
    rx = [s for s in syms if s.is_reexport and s.name == "Thing"][0]
    assert rx.extractor == "rustdoc-json" and rx.rung == "resolution"
    assert rx.exported_path == "mycrate::Thing"
    assert rx.canonical_path == "mycrate::inner::Thing"
    assert rx.filepath == "src/inner.rs" and rx.line_start == 3


def test_impl_methods_resolve_to_parent_type():
    syms = load_rust_rustdoc(FIX)
    method = [s for s in syms if s.kind == "method" and s.name == "new"][0]
    assert method.extractor == "rustdoc-json" and method.rung == "resolution"
    assert method.parent == "Thing"
    assert method.qualified_name == "mycrate::inner::Thing::new"
    assert method.canonical_path == "mycrate::inner::Thing::new"
    assert method.filepath == "src/inner.rs" and method.line_start == 8
    assert not any(s.kind == "function" and s.name == "new" for s in syms)


def test_blanket_impl_methods_are_skipped(tmp_path):
    base = json.loads(FIX.read_text())
    base["index"]["5"] = {
        "id": 5,
        "crate_id": 0,
        "name": None,
        "span": None,
        "visibility": "public",
        "docs": None,
        "inner": {
            "impl": {
                "is_unsafe": False,
                "generics": {"params": [], "where_predicates": []},
                "provided_trait_methods": [],
                "trait": {"path": "ToOwned", "id": 10, "args": None},
                "for": {"resolved_path": {"path": "mycrate::inner::Thing", "id": 1}},
                "items": [6],
                "negative": False,
                "synthetic": False,
                "blanket_impl": {"generic": "T"},
            }
        },
    }
    base["index"]["6"] = {
        "id": 6,
        "crate_id": 0,
        "name": "to_owned",
        "span": None,
        "visibility": "public",
        "docs": None,
        "inner": {"function": {"sig": {"inputs": [], "output": None, "is_c_variadic": False}}},
    }
    p = tmp_path / "with_blanket_impl.json"
    p.write_text(json.dumps(base))
    syms = load_rust_rustdoc(p)
    assert not any(s.kind == "method" and s.name == "to_owned" for s in syms)


def test_unsupported_format_version_hard_fails(tmp_path):
    bad = json.loads(FIX.read_text())
    bad["format_version"] = 999
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match=r"unsupported rustdoc format_version"):
        load_rust_rustdoc(p)
    # opt-out works:
    assert load_rust_rustdoc(p, allow_version_mismatch=True) is not None


def test_glob_reexport_with_null_id_is_skipped(tmp_path):
    """A pub use foo::* item has id=null; loader must skip it, not emit a half-resolved row."""
    base = json.loads(FIX.read_text())
    # Inject a glob re-export item: id=null signals an unresolved glob in format_version 57
    base["index"]["99"] = {
        "id": 99,
        "crate_id": 0,
        "name": "GlobReexport",
        "span": None,
        "visibility": "public",
        "docs": None,
        "inner": {
            "use": {"source": "somemod::*", "name": "GlobReexport", "id": None, "is_glob": True}
        },
    }
    p = tmp_path / "with_glob.json"
    p.write_text(json.dumps(base))
    syms = load_rust_rustdoc(p)
    # No symbol should be produced for the unresolved glob re-export
    assert not any(s.name == "GlobReexport" for s in syms)
    # Existing symbols are still produced (loader did not raise)
    assert any(s.is_reexport and s.name == "Thing" for s in syms)
