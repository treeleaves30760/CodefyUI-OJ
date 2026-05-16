"""Built-in scorers for OJ judge.

Each scorer takes:
- extracted_outputs: dict of `save_as` → raw value (numbers, lists, numpy arrays, tensors)
- scoring_spec: dict {method, target_output, ground_truth, threshold, full_score}
- hidden_data_dir: filesystem path containing ground truth files (CSV)

Returns: (score, log) tuple. score is float in [0, full_score]; log is human-readable diagnostic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class ScoringFailure(Exception):
    pass


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        return list(value.tolist())
    if hasattr(value, "cpu"):
        return list(value.cpu().tolist())
    if isinstance(value, (list, tuple)):
        return list(value)
    raise ScoringFailure(f"Cannot convert {type(value).__name__} to list")


def _load_csv_column(path: Path, dtype: str = "auto") -> list[Any]:
    text = path.read_text(encoding="utf-8").strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    first = lines[0].split(",")
    if len(first) > 1:
        try:
            float(first[0])
            rows = lines
        except ValueError:
            rows = lines[1:]
        return [r.split(",")[-1].strip() for r in rows]
    try:
        float(first[0])
        rows = lines
    except ValueError:
        rows = lines[1:]
    return [r.strip() for r in rows]


def _resolve_path(value: str, hidden_data_dir: str) -> Path:
    return Path(value.replace("{hidden_test_data}", hidden_data_dir))


def _coerce(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for v in values:
        if isinstance(v, str):
            try:
                out.append(float(v) if "." in v or "e" in v.lower() else int(v))
            except ValueError:
                out.append(v)
        else:
            out.append(v)
    return out


def score_accuracy(
    outputs: dict[str, Any], spec: dict[str, Any], hidden_data_dir: str
) -> tuple[float, str]:
    y_pred = _coerce(_to_list(outputs[spec["target_output"]]))
    gt_path = _resolve_path(spec["ground_truth"], hidden_data_dir)
    y_true = _coerce(_load_csv_column(gt_path))
    if len(y_pred) != len(y_true):
        raise ScoringFailure(
            f"Prediction length {len(y_pred)} != ground truth length {len(y_true)}"
        )
    n = len(y_true)
    if n == 0:
        raise ScoringFailure("Empty ground truth")
    correct = sum(1 for a, b in zip(y_pred, y_true) if a == b)
    acc = correct / n
    full = float(spec.get("full_score", 100))
    threshold = float(spec.get("threshold", 0.0))
    if threshold <= 0:
        score = acc * full
    else:
        score = full if acc >= threshold else (acc / threshold) * full
    return score, f"accuracy={acc:.4f} ({correct}/{n}); threshold={threshold}; score={score:.2f}/{full}"


def score_mse(
    outputs: dict[str, Any], spec: dict[str, Any], hidden_data_dir: str
) -> tuple[float, str]:
    y_pred = _coerce(_to_list(outputs[spec["target_output"]]))
    gt_path = _resolve_path(spec["ground_truth"], hidden_data_dir)
    y_true = _coerce(_load_csv_column(gt_path))
    if len(y_pred) != len(y_true):
        raise ScoringFailure(
            f"Prediction length {len(y_pred)} != ground truth length {len(y_true)}"
        )
    diffs = [(float(a) - float(b)) ** 2 for a, b in zip(y_pred, y_true)]
    mse = sum(diffs) / len(diffs)
    full = float(spec.get("full_score", 100))
    threshold = float(spec.get("threshold", 0.0))
    if threshold <= 0:
        score = full / (1.0 + mse)
    else:
        score = full if mse <= threshold else max(0.0, full * (threshold / mse))
    return score, f"mse={mse:.6f}; threshold={threshold}; score={score:.2f}/{full}"


def score_mae(
    outputs: dict[str, Any], spec: dict[str, Any], hidden_data_dir: str
) -> tuple[float, str]:
    y_pred = _coerce(_to_list(outputs[spec["target_output"]]))
    gt_path = _resolve_path(spec["ground_truth"], hidden_data_dir)
    y_true = _coerce(_load_csv_column(gt_path))
    if len(y_pred) != len(y_true):
        raise ScoringFailure(
            f"Prediction length {len(y_pred)} != ground truth length {len(y_true)}"
        )
    diffs = [abs(float(a) - float(b)) for a, b in zip(y_pred, y_true)]
    mae = sum(diffs) / len(diffs)
    full = float(spec.get("full_score", 100))
    threshold = float(spec.get("threshold", 0.0))
    if threshold <= 0:
        score = full / (1.0 + mae)
    else:
        score = full if mae <= threshold else max(0.0, full * (threshold / mae))
    return score, f"mae={mae:.6f}; threshold={threshold}; score={score:.2f}/{full}"


def score_exact_match(
    outputs: dict[str, Any], spec: dict[str, Any], hidden_data_dir: str
) -> tuple[float, str]:
    y_pred = _to_list(outputs[spec["target_output"]])
    gt_path = _resolve_path(spec["ground_truth"], hidden_data_dir)
    y_true = _load_csv_column(gt_path)
    full = float(spec.get("full_score", 100))
    if _coerce(y_pred) == _coerce(y_true):
        return full, f"exact match; score={full}/{full}"
    return 0.0, f"mismatch; score=0/{full}"


SCORERS = {
    "accuracy": score_accuracy,
    "mse": score_mse,
    "mae": score_mae,
    "exact_match": score_exact_match,
}


def compute_score(
    outputs: dict[str, Any], scoring_spec: dict[str, Any], hidden_data_dir: str
) -> tuple[float, str]:
    method = scoring_spec.get("method")
    scorer = SCORERS.get(method)
    if scorer is None:
        raise ScoringFailure(f"Unknown scoring method: {method!r}")
    return scorer(outputs, scoring_spec, hidden_data_dir)
