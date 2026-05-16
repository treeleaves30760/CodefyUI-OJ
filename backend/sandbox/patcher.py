"""Pure JSON manipulation for OJ judge.

Patches an uploaded graph JSON according to a judge_spec so that
input-feeding nodes point at hidden test data, before execution.
"""
from __future__ import annotations

import copy
from typing import Any


class ValidationFailure(Exception):
    """Raised when student submission is structurally invalid for this problem."""


def validate_required_nodes(graph: dict[str, Any], required_ids: list[str]) -> None:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValidationFailure("Submission missing 'nodes' array")
    existing = {n.get("id") for n in nodes if isinstance(n, dict)}
    missing = set(required_ids) - existing
    if missing:
        raise ValidationFailure(
            f"Submission missing required node IDs: {sorted(missing)}"
        )


def apply_patches(
    graph: dict[str, Any], spec: dict[str, Any], hidden_data_dir: str
) -> dict[str, Any]:
    """Return a deep-copied graph with input_patches applied.

    Variable `{hidden_test_data}` inside string param values is expanded
    to `hidden_data_dir`. The student's own values are otherwise preserved.
    """
    patched = copy.deepcopy(graph)
    nodes_by_id: dict[str, dict[str, Any]] = {
        n["id"]: n for n in patched.get("nodes", []) if isinstance(n, dict) and "id" in n
    }
    for patch in spec.get("input_patches", []):
        node = nodes_by_id.get(patch["node_id"])
        if node is None:
            continue
        data = node.setdefault("data", {})
        params = data.setdefault("params", {})
        for key, value in patch.get("param_overrides", {}).items():
            params[key] = _expand(value, hidden_data_dir)
    return patched


def _expand(value: Any, hidden_data_dir: str) -> Any:
    if isinstance(value, str):
        return value.replace("{hidden_test_data}", hidden_data_dir)
    if isinstance(value, list):
        return [_expand(v, hidden_data_dir) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v, hidden_data_dir) for k, v in value.items()}
    return value


def extract_outputs(
    execution_outputs: dict[str, dict[str, Any]],
    output_reads: list[dict[str, str]],
) -> dict[str, Any]:
    """Pull each declared OutputRead from cdui execute_graph result."""
    extracted: dict[str, Any] = {}
    for read in output_reads:
        nid = read["node_id"]
        port = read.get("port", "output")
        save_as = read["save_as"]
        if nid not in execution_outputs:
            raise ValidationFailure(f"Node '{nid}' produced no outputs")
        node_outputs = execution_outputs[nid]
        if port not in node_outputs:
            raise ValidationFailure(
                f"Node '{nid}' has no output port '{port}' (available: {list(node_outputs)})"
            )
        extracted[save_as] = node_outputs[port]
    return extracted
