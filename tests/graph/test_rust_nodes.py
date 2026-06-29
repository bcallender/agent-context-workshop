import json
from pathlib import Path

from context_workshop.graph.rust import prepare_nodes
from context_workshop.parsers import load_rust_rustdoc

FIX = Path(__file__).parent.parent / "fixtures" / "rustdoc_min.json"


def test_reexport_collapses_into_canonical_node():
    data = json.loads(FIX.read_text())
    nodes = prepare_nodes(load_rust_rustdoc(FIX), data)
    by_qn = {n["qualified_name"]: n for n in nodes}
    # No standalone re-export node at the exported path:
    assert "mycrate::Thing" not in by_qn
    # The canonical node carries the exported path:
    thing = by_qn["mycrate::inner::Thing"]
    assert "mycrate::Thing" in thing["exported_paths"]
    assert thing["crate"] == "mycrate"


def test_effective_public_true_for_public_chain():
    data = json.loads(FIX.read_text())
    nodes = prepare_nodes(load_rust_rustdoc(FIX), data)
    thing = {n["qualified_name"]: n for n in nodes}["mycrate::inner::Thing"]
    assert thing["effective_public"] is True


def test_effective_public_false_when_module_ancestor_is_private(tmp_path):
    """A pub struct inside a restricted (private) module must NOT be effective-public."""
    base = json.loads(FIX.read_text())

    # Inject a private module (id=10) as a child of the crate root
    base["index"]["10"] = {
        "id": 10,
        "crate_id": 0,
        "name": "hidden",
        "span": None,
        "visibility": "restricted",  # NOT "public"
        "docs": None,
        "inner": {"module": {"is_crate": False, "items": [11], "is_stripped": False}},
    }
    # Inject a pub struct (id=11) inside the private module
    base["index"]["11"] = {
        "id": 11,
        "crate_id": 0,
        "name": "Secret",
        "span": {"filename": "src/hidden.rs", "begin": [1, 1], "end": [3, 2]},
        "visibility": "public",
        "docs": None,
        "inner": {"struct": {"kind": {"unit": True}}},
    }
    # Add paths entries so _effective_public_paths can resolve them
    base["paths"]["10"] = {"crate_id": 0, "path": ["mycrate", "hidden"], "kind": "module"}
    base["paths"]["11"] = {"crate_id": 0, "path": ["mycrate", "hidden", "Secret"], "kind": "struct"}
    # Register the private module as a child of the crate root (id=0)
    base["index"]["0"]["inner"]["module"]["items"].append(10)

    p = tmp_path / "with_private_mod.json"
    p.write_text(json.dumps(base))

    nodes = prepare_nodes(load_rust_rustdoc(p), base)
    by_qn = {n["qualified_name"]: n for n in nodes}
    assert "mycrate::hidden::Secret" in by_qn, "Secret struct should be parsed as a symbol"
    assert by_qn["mycrate::hidden::Secret"]["effective_public"] is False
