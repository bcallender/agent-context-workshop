from pathlib import Path

from context_workshop.parsers.python_griffe import (
    extract_python_symbols,
    load_python_package,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load():
    mod = load_python_package("pypkg", search_paths=[FIXTURES])
    return extract_python_symbols(mod)


def test_extracts_the_defined_function():
    syms = _load()
    fn = [s for s in syms if s.qualified_name == "pypkg.mod.thing"]
    assert fn and fn[0].kind == "function"
    assert fn[0].extractor == "griffe" and fn[0].rung == "resolution"
    assert fn[0].parameters == ["a", "b"]


def test_reexport_resolves_to_canonical_definition():
    syms = _load()
    rx = [s for s in syms if s.is_reexport and s.name == "thing"]
    assert rx, "the __all__ re-export of `thing` should produce a reexport row"
    assert rx[0].exported_path == "pypkg.thing"  # where it's written
    assert rx[0].canonical_path == "pypkg.mod.thing"  # resolved def site
