import pytest

from sandbox.patcher import (
    ValidationFailure,
    apply_patches,
    extract_outputs,
    validate_required_nodes,
)


def test_validate_required_nodes_ok():
    graph = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": []}
    validate_required_nodes(graph, ["a", "b"])


def test_validate_required_nodes_missing():
    graph = {"nodes": [{"id": "a"}], "edges": []}
    with pytest.raises(ValidationFailure, match="missing required node IDs"):
        validate_required_nodes(graph, ["a", "b"])


def test_validate_required_nodes_missing_nodes_array():
    graph = {"edges": []}
    with pytest.raises(ValidationFailure, match="missing 'nodes'"):
        validate_required_nodes(graph, ["a"])


def test_apply_patches_overrides_params():
    graph = {
        "nodes": [
            {"id": "__INPUT__", "type": "CSVReader", "data": {"params": {"path": "old.csv"}}},
            {"id": "x", "type": "Other", "data": {"params": {"k": 1}}},
        ],
        "edges": [],
    }
    spec = {
        "input_patches": [
            {"node_id": "__INPUT__", "param_overrides": {"path": "{hidden_test_data}/X_test.csv"}},
        ]
    }
    patched = apply_patches(graph, spec, "/judge/data")

    assert patched["nodes"][0]["data"]["params"]["path"] == "/judge/data/X_test.csv"
    assert patched["nodes"][1]["data"]["params"]["k"] == 1
    assert graph["nodes"][0]["data"]["params"]["path"] == "old.csv"


def test_apply_patches_expands_nested_strings():
    graph = {
        "nodes": [{"id": "n", "data": {"params": {"paths": ["{hidden_test_data}/a", "static"]}}}],
        "edges": [],
    }
    spec = {
        "input_patches": [
            {"node_id": "n", "param_overrides": {"paths": ["{hidden_test_data}/x", "{hidden_test_data}/y"]}},
        ]
    }
    patched = apply_patches(graph, spec, "/d")
    assert patched["nodes"][0]["data"]["params"]["paths"] == ["/d/x", "/d/y"]


def test_apply_patches_creates_missing_data_params():
    graph = {"nodes": [{"id": "n", "type": "T"}], "edges": []}
    spec = {"input_patches": [{"node_id": "n", "param_overrides": {"k": "v"}}]}
    patched = apply_patches(graph, spec, "/d")
    assert patched["nodes"][0]["data"]["params"]["k"] == "v"


def test_apply_patches_ignores_unknown_node():
    graph = {"nodes": [{"id": "n"}], "edges": []}
    spec = {"input_patches": [{"node_id": "missing", "param_overrides": {"k": "v"}}]}
    patched = apply_patches(graph, spec, "/d")
    assert patched["nodes"][0] == graph["nodes"][0]


def test_extract_outputs_ok():
    execution = {
        "__SUBMIT__": {"value": [1, 2, 3], "extra": "ignored"},
        "intermediate": {"x": 99},
    }
    reads = [{"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"}]
    extracted = extract_outputs(execution, reads)
    assert extracted == {"y_pred": [1, 2, 3]}


def test_extract_outputs_missing_node():
    with pytest.raises(ValidationFailure, match="no outputs"):
        extract_outputs({}, [{"node_id": "n", "port": "p", "save_as": "x"}])


def test_extract_outputs_missing_port():
    execution = {"n": {"a": 1}}
    with pytest.raises(ValidationFailure, match="no output port"):
        extract_outputs(execution, [{"node_id": "n", "port": "z", "save_as": "x"}])
