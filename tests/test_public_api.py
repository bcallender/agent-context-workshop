import context_workshop.parsers as p


def test_public_api_surface():
    for name in (
        "Symbol",
        "rows",
        "fenic_schema",
        "load_python_package",
        "extract_python_symbols",
        "extract_rust_source",
        "extract_rust_crate",
        "load_rust_rustdoc",
        "build_tree",
        "tree_to_string",
    ):
        assert hasattr(p, name), f"missing public export: {name}"
