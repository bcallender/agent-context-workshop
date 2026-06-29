import pytest
from pydantic import ValidationError

from context_workshop.parsers.schema import Symbol, rows


def _min(**kw):
    base = dict(
        language="python",
        kind="function",
        name="f",
        qualified_name="m.f",
        extractor="griffe",
        rung="resolution",
    )
    base.update(kw)
    return Symbol(**base)


def test_rung_must_be_valid():
    with pytest.raises(ValidationError):
        _min(rung="semantic")  # not an allowed value


def test_extractor_must_be_valid():
    with pytest.raises(ValidationError):
        _min(extractor="clang")


def test_rows_are_plain_jsonable_dicts():
    out = rows([_min(parameters=["x"], bases=None)])
    assert isinstance(out, list) and isinstance(out[0], dict)
    r = out[0]
    assert r["rung"] == "resolution"
    assert r["parameters"] == ["x"]  # list[str] preserved
    assert r["bases"] is None  # None preserved (N/A for this language)
    assert r["is_public"] is False  # default applied


def test_symbol_fields_are_primitive_only():
    # guards the "primitive-only" constraint: every field annotation is str/int/bool/list[str]/None
    import dataclasses

    allowed = {"str", "int", "bool", "list[str]", "list", "Literal"}
    for f in dataclasses.fields(Symbol):
        ann = str(f.type)
        assert any(tok in ann for tok in allowed), f"{f.name} has non-primitive type {ann}"
