from pathlib import Path

import pytest

from sandbox.scoring import ScoringFailure, compute_score


@pytest.fixture
def hidden_dir(tmp_path: Path) -> str:
    return str(tmp_path)


def _write(tmp_path: Path, name: str, lines: list[str]) -> None:
    (tmp_path / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_accuracy_perfect(tmp_path):
    _write(tmp_path, "y.csv", ["1", "2", "3"])
    spec = {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "threshold": 0.0,
        "full_score": 100,
    }
    score, log = compute_score({"y_pred": [1, 2, 3]}, spec, str(tmp_path))
    assert score == 100.0
    assert "accuracy=1.0000" in log


def test_accuracy_partial_no_threshold(tmp_path):
    _write(tmp_path, "y.csv", ["1", "2", "3", "4"])
    spec = {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    }
    score, _ = compute_score({"y_pred": [1, 2, 0, 0]}, spec, str(tmp_path))
    assert score == 50.0


def test_accuracy_threshold_pass(tmp_path):
    _write(tmp_path, "y.csv", ["1", "1", "1", "1"])
    spec = {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "threshold": 0.75,
        "full_score": 100,
    }
    score, _ = compute_score({"y_pred": [1, 1, 1, 0]}, spec, str(tmp_path))
    assert score == 100.0


def test_accuracy_threshold_fail(tmp_path):
    _write(tmp_path, "y.csv", ["1", "1", "1", "1"])
    spec = {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "threshold": 0.8,
        "full_score": 100,
    }
    score, _ = compute_score({"y_pred": [1, 0, 0, 0]}, spec, str(tmp_path))
    assert score == pytest.approx((0.25 / 0.8) * 100)


def test_accuracy_length_mismatch_raises(tmp_path):
    _write(tmp_path, "y.csv", ["1", "2"])
    spec = {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    }
    with pytest.raises(ScoringFailure):
        compute_score({"y_pred": [1, 2, 3]}, spec, str(tmp_path))


def test_mse(tmp_path):
    _write(tmp_path, "y.csv", ["1.0", "2.0", "3.0"])
    spec = {
        "method": "mse",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    }
    score, log = compute_score({"y_pred": [1.0, 2.0, 3.0]}, spec, str(tmp_path))
    assert score == pytest.approx(100.0)
    assert "mse=0.000000" in log


def test_mse_with_threshold(tmp_path):
    _write(tmp_path, "y.csv", ["0", "0", "0"])
    spec = {
        "method": "mse",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "threshold": 0.5,
        "full_score": 100,
    }
    score_pass, _ = compute_score({"y_pred": [0.5, 0.5, 0.5]}, spec, str(tmp_path))
    assert score_pass == 100.0
    score_fail, _ = compute_score({"y_pred": [1.0, 1.0, 1.0]}, spec, str(tmp_path))
    assert 0 < score_fail < 100


def test_mae(tmp_path):
    _write(tmp_path, "y.csv", ["1.0", "2.0", "3.0"])
    spec = {
        "method": "mae",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    }
    score, log = compute_score({"y_pred": [1.0, 2.0, 4.0]}, spec, str(tmp_path))
    expected_mae = 1.0 / 3.0
    assert score == pytest.approx(100.0 / (1.0 + expected_mae))


def test_exact_match_pass(tmp_path):
    _write(tmp_path, "y.csv", ["1", "2", "3"])
    spec = {
        "method": "exact_match",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 50,
    }
    score, _ = compute_score({"y_pred": [1, 2, 3]}, spec, str(tmp_path))
    assert score == 50.0


def test_exact_match_fail(tmp_path):
    _write(tmp_path, "y.csv", ["1", "2", "3"])
    spec = {
        "method": "exact_match",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 50,
    }
    score, _ = compute_score({"y_pred": [1, 2, 4]}, spec, str(tmp_path))
    assert score == 0.0


def test_csv_with_header(tmp_path):
    _write(tmp_path, "y.csv", ["label", "1", "2", "3"])
    spec = {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    }
    score, _ = compute_score({"y_pred": [1, 2, 3]}, spec, str(tmp_path))
    assert score == 100.0


def test_unknown_method(tmp_path):
    spec = {"method": "wat", "target_output": "y", "full_score": 1}
    with pytest.raises(ScoringFailure):
        compute_score({"y": [1]}, spec, str(tmp_path))
