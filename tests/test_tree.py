from context_workshop.parsers.schema import Symbol, rows
from context_workshop.parsers.tree import build_tree, tree_to_string


def _symbol(**overrides):
    base = dict(
        language="python",
        kind="function",
        name="f",
        qualified_name="pkg.mod.f",
        extractor="griffe",
        rung="resolution",
    )
    base.update(overrides)
    return Symbol(**base)


def test_build_tree_uses_symbol_kind_and_language_separators():
    tree = build_tree(
        rows(
            [
                _symbol(kind="method", name="run", qualified_name="pkg.mod.Widget.run"),
                _symbol(kind="class", name="Widget", qualified_name="pkg.mod.Widget"),
                _symbol(
                    language="rust",
                    kind="struct",
                    name="Widget",
                    qualified_name="demo::api::Widget",
                    extractor="tree-sitter",
                    rung="syntactic",
                ),
                _symbol(
                    language="rust",
                    kind="function",
                    name="build",
                    qualified_name="demo::api::build",
                    extractor="tree-sitter",
                    rung="syntactic",
                ),
            ]
        )
    )

    py_widget = tree["children"]["pkg"]["children"]["mod"]["children"]["Widget"]
    rust_api = tree["children"]["demo"]["children"]["api"]

    assert py_widget["kind"] == "class"
    assert py_widget["children"]["run"]["kind"] == "method"
    assert rust_api["children"]["Widget"]["kind"] == "struct"
    assert rust_api["children"]["build"]["kind"] == "function"
    assert "demo::api::Widget" not in tree["children"]


def test_tree_to_string_renders_symbol_tree():
    tree = build_tree(
        rows(
            [
                _symbol(kind="class", name="Widget", qualified_name="pkg.mod.Widget"),
                _symbol(
                    language="rust",
                    kind="struct",
                    name="Config",
                    qualified_name="demo::api::Config",
                    extractor="tree-sitter",
                    rung="syntactic",
                ),
            ]
        )
    )

    rendered = tree_to_string(tree, max_depth=4)

    assert "[class] Widget" in rendered
    assert "[struct] Config" in rendered
