"""One-shot generator for reference solution graph.json files.

Run from the repo root via:
    python docs/reference_solutions/_generate.py

The output graphs mirror the structure expected by cdui's execute_graph:
- Start node fires triggers to both CSV readers.
- A model node (KNN / LogisticRegression / SVMClassifier / LinearRegression) is
  fed by __TRAIN__.tensor + __TRAIN__.labels and queried with __TEST_X__.tensor.
- For problems with very different feature scales, a Normalize(zscore) stage is
  reused for x_train and x_query.
- model.predictions lands on __SUBMIT__.value.

These files are pedagogical reference, not unit-test fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).resolve().parent

# ---- Per-problem spec: (slug, model_type, model_params, normalize) ----------
SOLUTIONS: list[tuple[str, str, dict[str, Any], bool]] = [
    ("warmup-passthrough", "passthrough", {}, False),
    ("iris-knn", "KNN", {"k": 5}, False),
    ("wine-logistic", "LogisticRegression", {"max_iter": 200}, True),
    ("customer-churn", "SVMClassifier", {"kernel": "rbf", "C": 1.0}, True),
    ("housing-linear", "LinearRegression", {}, False),
    ("fruit-basket-knn", "KNN", {"k": 3}, False),
    ("coin-fairness", "LogisticRegression", {"max_iter": 200}, False),
    ("weather-rain-svm", "SVMClassifier", {"kernel": "rbf", "C": 1.0}, True),
    ("seed-variety-knn", "KNN", {"k": 5}, False),
    ("mushroom-edible", "KNN", {"k": 5}, False),
    ("diabetes-screen", "LogisticRegression", {"max_iter": 300}, True),
    ("fish-species", "KNN", {"k": 3}, False),
    ("credit-approval", "LogisticRegression", {"max_iter": 200}, True),
    ("student-pass", "LogisticRegression", {"max_iter": 200}, False),
    ("stellar-type", "KNN", {"k": 5}, True),
    ("car-price", "LinearRegression", {}, False),
    ("salary-experience", "LinearRegression", {}, False),
    ("crop-yield", "LinearRegression", {}, False),
    ("electricity-demand", "LinearRegression", {}, True),
    ("solar-output", "LinearRegression", {}, False),
]


def _node(node_id: str, type_: str, x: int, y: int, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": type_,
        "position": {"x": x, "y": y},
        "data": {"params": params},
    }


def _trigger_edge(src: str, tgt: str) -> dict[str, Any]:
    return {
        "id": f"trig_{tgt}",
        "source": src,
        "target": tgt,
        "sourceHandle": "trigger",
        "type": "trigger",
    }


def _data_edge(src: str, src_port: str, tgt: str, tgt_port: str) -> dict[str, Any]:
    return {
        "id": f"{src}_{src_port}__{tgt}_{tgt_port}",
        "source": src,
        "target": tgt,
        "sourceHandle": src_port,
        "targetHandle": tgt_port,
        "type": "data",
    }


def _readers(target_column: str = "label", include_columns: str = "*") -> list[dict[str, Any]]:
    return [
        _node(
            "__TRAIN__",
            "CSVReader",
            80,
            -120,
            {
                "path": "data/samples/train.csv",
                "target_column": target_column,
                "include_columns": include_columns,
                "skip_header": True,
            },
        ),
        _node(
            "__TEST_X__",
            "CSVReader",
            80,
            120,
            {
                "path": "data/samples/test.csv",
                "target_column": "",
                "include_columns": include_columns,
                "skip_header": True,
            },
        ),
    ]


def build_passthrough() -> dict[str, Any]:
    nodes = [
        _node("start", "Start", -200, 0, {}),
        *_readers(),
        _node("__SUBMIT__", "Print", 720, 0, {"label": "predictions"}),
    ]
    edges = [
        _trigger_edge("start", "__TRAIN__"),
        _trigger_edge("start", "__TEST_X__"),
        _data_edge("__TRAIN__", "labels", "__SUBMIT__", "value"),
    ]
    return {"name": "Reference — passthrough", "nodes": nodes, "edges": edges}


def build_model_solution(model_type: str, model_params: dict[str, Any], normalize: bool) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        _node("start", "Start", -200, 0, {}),
        *_readers(),
    ]

    model_id = "model"
    if normalize:
        nodes += [
            _node("norm_train", "Normalize", 320, -120, {"method": "zscore"}),
            _node("norm_query", "Normalize", 320, 120, {"method": "zscore"}),
        ]

    nodes.append(_node(model_id, model_type, 520, 0, model_params))
    nodes.append(_node("__SUBMIT__", "Print", 720, 0, {"label": "predictions"}))

    edges = [
        _trigger_edge("start", "__TRAIN__"),
        _trigger_edge("start", "__TEST_X__"),
    ]

    if normalize:
        edges += [
            _data_edge("__TRAIN__", "tensor", "norm_train", "input"),
            _data_edge("__TEST_X__", "tensor", "norm_query", "input"),
            _data_edge("norm_train", "output", model_id, "x_train"),
            _data_edge("norm_query", "output", model_id, "x_query"),
        ]
    else:
        edges += [
            _data_edge("__TRAIN__", "tensor", model_id, "x_train"),
            _data_edge("__TEST_X__", "tensor", model_id, "x_query"),
        ]

    edges += [
        _data_edge("__TRAIN__", "labels", model_id, "y_train"),
        _data_edge(model_id, "predictions", "__SUBMIT__", "value"),
    ]

    pretty = f"{'Normalize → ' if normalize else ''}{model_type}"
    return {"name": f"Reference — {pretty}", "nodes": nodes, "edges": edges}


def main() -> None:
    for slug, model_type, model_params, normalize in SOLUTIONS:
        if model_type == "passthrough":
            graph = build_passthrough()
        else:
            graph = build_model_solution(model_type, model_params, normalize)
        out = OUT_DIR / f"{slug}.json"
        out.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out.relative_to(OUT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
