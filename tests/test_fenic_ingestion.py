import dataclasses

import fenic as fc

from context_workshop.parsers.schema import _FIELDS, Symbol, fenic_schema, to_arrow


def _py(**kw):
    b = dict(
        language="python",
        kind="function",
        name="f",
        qualified_name="m.f",
        extractor="griffe",
        rung="resolution",
        parameters=[],
        bases=None,
    )
    b.update(kw)
    return Symbol(**b)


def _rs(**kw):
    b = dict(
        language="rust",
        kind="struct",
        name="S",
        qualified_name="c::S",
        extractor="tree-sitter",
        rung="syntactic",
        parameters=None,
        bases=None,
        cfg_gated=False,
    )
    b.update(kw)
    return Symbol(**b)


def test_schema_fields_match_contract():
    names = {n for n, _ in _FIELDS}
    assert names == {f.name for f in dataclasses.fields(Symbol)}  # _FIELDS in sync with Symbol
    assert {cf.name for cf in fenic_schema().column_fields} == names  # fenic schema in sync


def test_mixed_python_rust_batch_ingests_via_forced_arrow_schema():
    # Raw create_dataframe(list_of_dicts) would raise TypeInferenceError on the
    # all-None `bases` column; the typed pyarrow Table forces correct types.
    batch = [_py(), _py(parameters=["x", "y"]), _rs(), _rs(cfg_gated=True)]
    session = fc.Session.get_or_create(fc.SessionConfig(app_name="parsers_test"))
    df = session.create_dataframe(to_arrow(batch))
    assert df.count() == 4
    bases_t = [c.data_type for c in df.schema.column_fields if c.name == "bases"][0]
    assert "ArrayType" in repr(bases_t)  # all-None bases stays array<string>, not Null
