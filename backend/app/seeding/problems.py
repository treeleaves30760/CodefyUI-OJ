"""Baseline problem definitions for the OJ.

Each seed bundles the starter template students download from the UI, the
judge_spec the grader follows, and the synthetic test data that ships with
the problem. All five share the same three required node IDs so students
build familiarity with the pattern:

* ``__TRAIN__`` — CSVReader pointed at the training file. ``target_column``
  splits the table into a feature tensor + label list.
* ``__TEST_X__`` — CSVReader pointed at the held-out features only.
* ``__SUBMIT__`` — Print node whose ``value`` output is what the judge
  compares against the hidden ground truth.

The student's job is to wire a model in between (and any preprocessing
they like) — the judge patches the two reader paths to point at the
unzipped hidden test data at run time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.models.problem import ProblemDifficulty
from app.seeding.datasets import (
    churn_like_dataset,
    housing_like_dataset,
    iris_like_dataset,
    warmup_passthrough_dataset,
    wine_like_dataset,
)


@dataclass(frozen=True)
class SeedProblem:
    slug: str
    title: str
    statement_md: str
    difficulty: ProblemDifficulty
    tags: list[str]
    points: int
    starter_template: dict[str, Any]
    judge_spec: dict[str, Any]
    dataset: Callable[[], tuple[str, str, str]]
    time_limit_seconds: int = 60
    memory_limit_mb: int = 2048


def _classification_template(
    train_path_default: str,
    test_path_default: str,
    target_column: str,
    feature_columns: list[str],
    description: str,
) -> dict[str, Any]:
    return {
        "name": f"Starter — {target_column} classification",
        "description": description,
        "nodes": [
            {
                "id": "start",
                "type": "Start",
                "position": {"x": -200, "y": 0},
                "data": {"params": {}},
            },
            {
                "id": "__TRAIN__",
                "type": "CSVReader",
                "position": {"x": 80, "y": -120},
                "data": {
                    "params": {
                        "path": train_path_default,
                        "target_column": target_column,
                        "include_columns": ",".join(feature_columns),
                        "skip_header": True,
                    }
                },
            },
            {
                "id": "__TEST_X__",
                "type": "CSVReader",
                "position": {"x": 80, "y": 120},
                "data": {
                    "params": {
                        "path": test_path_default,
                        "target_column": "",
                        "include_columns": ",".join(feature_columns),
                        "skip_header": True,
                    }
                },
            },
            {
                "id": "__SUBMIT__",
                "type": "Print",
                "position": {"x": 720, "y": 0},
                "data": {"params": {"label": "predictions"}},
            },
        ],
        "edges": [
            {
                "id": "trig_train",
                "source": "start",
                "target": "__TRAIN__",
                "sourceHandle": "trigger",
                "type": "trigger",
            },
            {
                "id": "trig_test",
                "source": "start",
                "target": "__TEST_X__",
                "sourceHandle": "trigger",
                "type": "trigger",
            },
        ],
    }


def _regression_template(
    train_path_default: str,
    test_path_default: str,
    target_column: str,
    feature_columns: list[str],
    description: str,
) -> dict[str, Any]:
    # Same shape as classification — CSVReader emits a tensor of features
    # plus a label list (regression target uses the labels output too).
    return _classification_template(
        train_path_default,
        test_path_default,
        target_column,
        feature_columns,
        description,
    )


def _classification_spec(
    feature_columns: list[str],
    target_column: str,
    *,
    threshold: float,
    full_score: float,
) -> dict[str, Any]:
    return {
        "required_node_ids": ["__TRAIN__", "__TEST_X__", "__SUBMIT__"],
        "input_patches": [
            {
                "node_id": "__TRAIN__",
                "param_overrides": {
                    "path": "{hidden_test_data}/train.csv",
                    "target_column": target_column,
                    "include_columns": ",".join(feature_columns),
                    "skip_header": True,
                },
            },
            {
                "node_id": "__TEST_X__",
                "param_overrides": {
                    "path": "{hidden_test_data}/test_features.csv",
                    "target_column": "",
                    "include_columns": ",".join(feature_columns),
                    "skip_header": True,
                },
            },
        ],
        "output_reads": [
            {"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"},
        ],
        "scoring": {
            "method": "accuracy",
            "target_output": "y_pred",
            "ground_truth": "{hidden_test_data}/test_labels.csv",
            "threshold": threshold,
            "full_score": full_score,
        },
        "time_limit_seconds": 60,
        "memory_limit_mb": 2048,
    }


def _regression_spec(
    feature_columns: list[str],
    target_column: str,
    *,
    threshold: float,
    full_score: float,
) -> dict[str, Any]:
    return {
        "required_node_ids": ["__TRAIN__", "__TEST_X__", "__SUBMIT__"],
        "input_patches": [
            {
                "node_id": "__TRAIN__",
                "param_overrides": {
                    "path": "{hidden_test_data}/train.csv",
                    "target_column": target_column,
                    "include_columns": ",".join(feature_columns),
                    "skip_header": True,
                },
            },
            {
                "node_id": "__TEST_X__",
                "param_overrides": {
                    "path": "{hidden_test_data}/test_features.csv",
                    "target_column": "",
                    "include_columns": ",".join(feature_columns),
                    "skip_header": True,
                },
            },
        ],
        "output_reads": [
            {"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"},
        ],
        "scoring": {
            "method": "mse",
            "target_output": "y_pred",
            "ground_truth": "{hidden_test_data}/test_labels.csv",
            "threshold": threshold,
            "full_score": full_score,
        },
        "time_limit_seconds": 60,
        "memory_limit_mb": 2048,
    }


WARMUP_FEATURES = ["r", "g", "b"]
WARMUP_TARGET = "colour"

IRIS_FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
IRIS_TARGET = "species"

WINE_FEATURES = ["alcohol", "malic_acid", "ash", "alcalinity", "magnesium"]
WINE_TARGET = "cultivar"

CHURN_FEATURES = [
    "tenure_years",
    "monthly_fee",
    "satisfaction",
    "support_calls",
    "missed_payments",
]
CHURN_TARGET = "churn_flag"

HOUSING_FEATURES = ["rooms", "age_years", "distance_metro_km", "crime_rate"]
HOUSING_TARGET = "price_k"


SEED_PROBLEMS: list[SeedProblem] = [
    SeedProblem(
        slug="warmup-passthrough",
        title="暖身：資料流直通 / Warmup: data passthrough",
        statement_md=(
            "## 任務 / Task\n\n"
            "把 CSV 的標籤直接交給 `__SUBMIT__`，熟悉 OJ 的圖形流程。"
            "Wire the training labels directly into `__SUBMIT__` — no model required.\n\n"
            "### 必要節點 / Required nodes\n"
            "- `__TRAIN__` — CSVReader，會輸出 `tensor` (特徵) 與 `labels` (顏色)。\n"
            "- `__TEST_X__` — 測試集 CSVReader（這題你不會用到它的特徵）。\n"
            "- `__SUBMIT__` — Print，請把 **訓練集的 labels** 接到 `value` 端口。\n\n"
            "判題時 `__TRAIN__.path` 會被換成隱藏測資的 `train.csv`，其中 `colour` 欄\n"
            "與 `test_labels.csv` 相同——只要正確接好線，就能拿到滿分。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["warmup", "io", "tutorial"],
        points=100,
        starter_template=_classification_template(
            train_path_default="data/samples/warmup.csv",
            test_path_default="data/samples/warmup_test.csv",
            target_column=WARMUP_TARGET,
            feature_columns=WARMUP_FEATURES,
            description="連 __TRAIN__.labels 到 __SUBMIT__.value 即可通過。",
        ),
        judge_spec={
            "required_node_ids": ["__TRAIN__", "__TEST_X__", "__SUBMIT__"],
            "input_patches": [
                {
                    "node_id": "__TRAIN__",
                    "param_overrides": {
                        "path": "{hidden_test_data}/test_features.csv",
                        "target_column": "",
                        "include_columns": ",".join(WARMUP_FEATURES),
                        "skip_header": True,
                    },
                },
                {
                    "node_id": "__TEST_X__",
                    "param_overrides": {
                        "path": "{hidden_test_data}/test_features.csv",
                        "target_column": "",
                        "include_columns": ",".join(WARMUP_FEATURES),
                        "skip_header": True,
                    },
                },
            ],
            "output_reads": [
                {"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"},
            ],
            "scoring": {
                "method": "accuracy",
                "target_output": "y_pred",
                "ground_truth": "{hidden_test_data}/test_labels.csv",
                "threshold": 0.95,
                "full_score": 100.0,
            },
            "time_limit_seconds": 30,
            "memory_limit_mb": 1024,
        },
        dataset=warmup_passthrough_dataset,
        time_limit_seconds=30,
        memory_limit_mb=1024,
    ),
    SeedProblem(
        slug="iris-knn",
        title="Iris 鳶尾花分類 / Iris KNN",
        statement_md=(
            "## 任務 / Task\n\n"
            "用 KNN（或其他分類器）對 Iris 三品種進行分類，目標準確率 ≥ 0.93。\n"
            "Classify three iris species with KNN; aim for accuracy ≥ 0.93.\n\n"
            "### 必要節點 / Required nodes\n"
            "- `__TRAIN__` — 訓練資料 CSVReader，`target_column=species`。\n"
            "- `__TEST_X__` — 測試特徵 CSVReader，無標籤欄。\n"
            "- `__SUBMIT__` — Print，請接到分類器的 `predictions`。\n\n"
            "### 建議連線 / Suggested wiring\n"
            "1. `__TRAIN__.tensor → KNN.x_train`\n"
            "2. `__TRAIN__.labels → KNN.y_train`\n"
            "3. `__TEST_X__.tensor → KNN.x_query`\n"
            "4. `KNN.predictions → __SUBMIT__.value`\n\n"
            "可以加上 Normalize 節點先做特徵縮放。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["classification", "knn", "iris"],
        points=200,
        starter_template=_classification_template(
            train_path_default="data/samples/iris.csv",
            test_path_default="data/samples/iris_test.csv",
            target_column=IRIS_TARGET,
            feature_columns=IRIS_FEATURES,
            description="把 KNN 接在 __TRAIN__、__TEST_X__、__SUBMIT__ 之間。",
        ),
        judge_spec=_classification_spec(
            IRIS_FEATURES, IRIS_TARGET, threshold=0.93, full_score=100.0
        ),
        dataset=iris_like_dataset,
    ),
    SeedProblem(
        slug="wine-logistic",
        title="葡萄酒品種辨識 / Wine multinomial",
        statement_md=(
            "## 任務 / Task\n\n"
            "用多元 Logistic Regression（或任何分類器）辨識 3 個葡萄酒品種，"
            "準確率目標 ≥ 0.90。\n"
            "Use multinomial Logistic Regression to identify three cultivars; "
            "target accuracy ≥ 0.90.\n\n"
            "建議先用 `Normalize`（zscore）對 5 個化學屬性做標準化，再餵給 "
            "`LogisticRegression`。\n"
            "Try `Normalize` (zscore) before `LogisticRegression` — features "
            "live on very different scales.\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["classification", "logistic-regression", "preprocessing"],
        points=300,
        starter_template=_classification_template(
            train_path_default="data/samples/wine.csv",
            test_path_default="data/samples/wine_test.csv",
            target_column=WINE_TARGET,
            feature_columns=WINE_FEATURES,
            description="先標準化，再用 LogisticRegression 預測 cultivar。",
        ),
        judge_spec=_classification_spec(
            WINE_FEATURES, WINE_TARGET, threshold=0.90, full_score=100.0
        ),
        dataset=wine_like_dataset,
    ),
    SeedProblem(
        slug="customer-churn",
        title="客戶流失二元分類 / Customer churn",
        statement_md=(
            "## 任務 / Task\n\n"
            "預測客戶是否會流失（`stay` / `churn`），準確率目標 ≥ 0.88。\n"
            "Predict whether a customer will churn; target accuracy ≥ 0.88.\n\n"
            "資料有 5 個欄位（年資、月費、滿意度、客服次數、漏繳次數），可用任意 "
            "分類器：KNN、LogisticRegression、SVMClassifier 都可以。\n"
            "Try any classifier — `SVMClassifier` with an RBF kernel tends to "
            "perform well on this layout.\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["classification", "binary", "tabular"],
        points=300,
        starter_template=_classification_template(
            train_path_default="data/samples/churn.csv",
            test_path_default="data/samples/churn_test.csv",
            target_column=CHURN_TARGET,
            feature_columns=CHURN_FEATURES,
            description="自由選擇分類器；建議標準化後使用 SVMClassifier 或 LogisticRegression。",
        ),
        judge_spec=_classification_spec(
            CHURN_FEATURES, CHURN_TARGET, threshold=0.88, full_score=100.0
        ),
        dataset=churn_like_dataset,
    ),
    SeedProblem(
        slug="housing-linear",
        title="房價線性迴歸 / Housing regression",
        statement_md=(
            "## 任務 / Task\n\n"
            "預測房價（單位：千元）。評分標準為 MSE，越小越好；MSE ≤ 4.0 拿滿分。\n"
            "Predict housing price (in thousands). Score is MSE — full marks at MSE ≤ 4.0.\n\n"
            "### 必要節點 / Required nodes\n"
            "- `__TRAIN__` — 訓練資料，`target_column=price_k`。\n"
            "- `__TEST_X__` — 測試特徵，無標籤欄。\n"
            "- `__SUBMIT__` — Print，請接到 `LinearRegression.predictions`。\n\n"
            "回歸題的輸出是浮點數張量，Print 會原樣傳遞給判題端。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["regression", "linear-regression"],
        points=300,
        starter_template=_regression_template(
            train_path_default="data/samples/housing.csv",
            test_path_default="data/samples/housing_test.csv",
            target_column=HOUSING_TARGET,
            feature_columns=HOUSING_FEATURES,
            description="把 LinearRegression 接在 __TRAIN__、__TEST_X__、__SUBMIT__ 之間。",
        ),
        judge_spec=_regression_spec(
            HOUSING_FEATURES, HOUSING_TARGET, threshold=4.0, full_score=100.0
        ),
        dataset=housing_like_dataset,
    ),
]


__all__ = ["SEED_PROBLEMS", "SeedProblem"]
