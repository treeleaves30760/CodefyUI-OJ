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
    car_price_dataset,
    churn_like_dataset,
    coin_balance_dataset,
    credit_approval_dataset,
    crop_yield_dataset,
    diabetes_screen_dataset,
    electricity_demand_dataset,
    fish_species_dataset,
    fruit_basket_dataset,
    housing_like_dataset,
    iris_like_dataset,
    mushroom_edible_dataset,
    salary_experience_dataset,
    seed_variety_dataset,
    solar_output_dataset,
    stellar_type_dataset,
    student_pass_dataset,
    warmup_passthrough_dataset,
    weather_rain_dataset,
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

# --- Extended seed problem feature/target tables ---
FRUIT_FEATURES = ["weight_g", "red_score", "yellow_score"]
FRUIT_TARGET = "fruit"

COIN_FEATURES = ["heads_ratio", "tails_ratio", "max_streak"]
COIN_TARGET = "coin_type"

WEATHER_FEATURES = ["temperature_c", "humidity_pct", "pressure_hpa"]
WEATHER_TARGET = "weather"

SEEDVAR_FEATURES = ["length", "width", "perimeter", "compactness"]
SEEDVAR_TARGET = "variety"

MUSHROOM_FEATURES = ["cap_cm", "stem_cm", "gill_dark_score", "odor_pungent_score"]
MUSHROOM_TARGET = "edible_flag"

DIABETES_FEATURES = ["glucose", "bmi", "age", "blood_pressure", "insulin"]
DIABETES_TARGET = "diabetes_label"

FISH_FEATURES = ["length_cm", "weight_g", "fin_ratio"]
FISH_TARGET = "species"

CREDIT_FEATURES = ["income_k", "debt_ratio", "credit_history_years", "employed_years", "defaults"]
CREDIT_TARGET = "decision"

STUDENT_FEATURES = ["study_hours_per_week", "attendance_pct", "prev_grade", "assignments_done_ratio"]
STUDENT_TARGET = "result"

STELLAR_FEATURES = ["brightness_norm", "log_temperature", "mass_solar", "radius_solar"]
STELLAR_TARGET = "stellar_type"

CARPRICE_FEATURES = ["age_years", "mileage_km10k", "engine_l", "horsepower"]
CARPRICE_TARGET = "price_k"

SALARY_FEATURES = ["years_experience", "education_years", "certifications"]
SALARY_TARGET = "salary_k"

CROP_FEATURES = ["rainfall_mm", "avg_temp_c", "fertilizer_kg", "soil_quality"]
CROP_TARGET = "yield_tons"

ELEC_FEATURES = ["hour", "temperature_c", "day_of_week", "is_holiday"]
ELEC_TARGET = "demand_mw"

SOLAR_FEATURES = ["sunlight_kwm2", "panel_efficiency", "temperature_c", "cloud_cover"]
SOLAR_TARGET = "output_kwh"


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
            "回歸題的輸出是浮點數張量，Print 會原樣傳遞給判題端。\n\n"
            "### 參考解法 / Reference solution\n"
            "`__TRAIN__.tensor → LinearRegression.x_train`、\n"
            "`__TRAIN__.labels → LinearRegression.y_train`、\n"
            "`__TEST_X__.tensor → LinearRegression.x_query`、\n"
            "`LinearRegression.predictions → __SUBMIT__.value`。\n"
            "無需做特徵縮放；資料本身已大致線性。\n"
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
    # ------------------------------------------------------------------
    # Extended problem set (15 more — brings the catalog to 20 problems)
    # ------------------------------------------------------------------
    SeedProblem(
        slug="fruit-basket-knn",
        title="水果分類 / Fruit basket KNN",
        statement_md=(
            "## 任務 / Task\n\n"
            "依照 `weight_g`、`red_score`、`yellow_score` 三項特徵判斷水果類別："
            "`apple` / `orange` / `banana`，目標準確率 ≥ 0.92。\n"
            "Classify fruits as apple / orange / banana using KNN; target accuracy ≥ 0.92.\n\n"
            "### 參考解法 / Reference solution\n"
            "三類質量、紅色與黃色分數的中心彼此分離很開，直接 `KNN(k=3)` 即可：\n"
            "`__TRAIN__.tensor → KNN.x_train` → `__TRAIN__.labels → KNN.y_train` → "
            "`__TEST_X__.tensor → KNN.x_query` → `KNN.predictions → __SUBMIT__.value`。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["classification", "knn", "fruit"],
        points=150,
        starter_template=_classification_template(
            train_path_default="data/samples/fruit.csv",
            test_path_default="data/samples/fruit_test.csv",
            target_column=FRUIT_TARGET,
            feature_columns=FRUIT_FEATURES,
            description="用 KNN 將水果分成 apple / orange / banana。",
        ),
        judge_spec=_classification_spec(
            FRUIT_FEATURES, FRUIT_TARGET, threshold=0.92, full_score=100.0
        ),
        dataset=fruit_basket_dataset,
    ),
    SeedProblem(
        slug="coin-fairness",
        title="硬幣公平性偵測 / Coin fairness",
        statement_md=(
            "## 任務 / Task\n\n"
            "從一段擲幣統計（正面比例、反面比例、最長同面連續次數）判斷硬幣是公平 "
            "（`fair`）還是有偏（`biased`）。目標準確率 ≥ 0.95。\n"
            "Decide whether a coin is fair or biased from observed session stats. "
            "Target accuracy ≥ 0.95.\n\n"
            "### 參考解法 / Reference solution\n"
            "兩類分得很開，`LogisticRegression` 或 `KNN(k=5)` 都能輕鬆滿分。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["classification", "binary", "logistic-regression"],
        points=150,
        starter_template=_classification_template(
            train_path_default="data/samples/coin.csv",
            test_path_default="data/samples/coin_test.csv",
            target_column=COIN_TARGET,
            feature_columns=COIN_FEATURES,
            description="用 LogisticRegression 判斷 fair / biased。",
        ),
        judge_spec=_classification_spec(
            COIN_FEATURES, COIN_TARGET, threshold=0.95, full_score=100.0
        ),
        dataset=coin_balance_dataset,
    ),
    SeedProblem(
        slug="weather-rain-svm",
        title="降雨二元分類 / Weather rain SVM",
        statement_md=(
            "## 任務 / Task\n\n"
            "用溫度、濕度、氣壓三個感測值預測明日是否下雨（`dry` / `rain`），"
            "準確率目標 ≥ 0.90。\n"
            "Predict tomorrow's weather (dry / rain) from temperature, humidity, "
            "and pressure. Target accuracy ≥ 0.90.\n\n"
            "### 參考解法 / Reference solution\n"
            "三個特徵尺度差很大，建議先 `Normalize(zscore)` 再餵給 `SVMClassifier`"
            "（RBF kernel）。`LogisticRegression` 也能達標。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["classification", "binary", "svm", "preprocessing"],
        points=250,
        starter_template=_classification_template(
            train_path_default="data/samples/weather.csv",
            test_path_default="data/samples/weather_test.csv",
            target_column=WEATHER_TARGET,
            feature_columns=WEATHER_FEATURES,
            description="先標準化，再用 SVMClassifier 預測天氣。",
        ),
        judge_spec=_classification_spec(
            WEATHER_FEATURES, WEATHER_TARGET, threshold=0.90, full_score=100.0
        ),
        dataset=weather_rain_dataset,
    ),
    SeedProblem(
        slug="seed-variety-knn",
        title="麥種品種分類 / Seed variety KNN",
        statement_md=(
            "## 任務 / Task\n\n"
            "用四項幾何特徵（長度、寬度、周長、緊緻度）分類 3 種麥粒品種，"
            "準確率 ≥ 0.90。\n"
            "Classify three wheat-grain varieties from geometric features; "
            "target accuracy ≥ 0.90.\n\n"
            "### 參考解法 / Reference solution\n"
            "`KNN(k=5)` 直接套上就能過。如果想要更穩，先 `Normalize` 再分類。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["classification", "knn", "agriculture"],
        points=250,
        starter_template=_classification_template(
            train_path_default="data/samples/seeds.csv",
            test_path_default="data/samples/seeds_test.csv",
            target_column=SEEDVAR_TARGET,
            feature_columns=SEEDVAR_FEATURES,
            description="用 KNN 對麥粒品種做三類分類。",
        ),
        judge_spec=_classification_spec(
            SEEDVAR_FEATURES, SEEDVAR_TARGET, threshold=0.90, full_score=100.0
        ),
        dataset=seed_variety_dataset,
    ),
    SeedProblem(
        slug="mushroom-edible",
        title="蘑菇可食性 / Mushroom edibility",
        statement_md=(
            "## 任務 / Task\n\n"
            "依照蘑菇的菌蓋大小、菌柄長度、菌褶顏色分數、氣味刺激分數，判斷是 "
            "`edible` 還是 `poisonous`。準確率 ≥ 0.93。\n"
            "Decide whether a mushroom is edible or poisonous. Target accuracy ≥ 0.93.\n\n"
            "### 參考解法 / Reference solution\n"
            "兩類分得非常開，KNN 或 SVMClassifier 任一都能拿滿。可不需要標準化。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["classification", "binary", "biology"],
        points=200,
        starter_template=_classification_template(
            train_path_default="data/samples/mushroom.csv",
            test_path_default="data/samples/mushroom_test.csv",
            target_column=MUSHROOM_TARGET,
            feature_columns=MUSHROOM_FEATURES,
            description="判斷蘑菇是 edible 或 poisonous。",
        ),
        judge_spec=_classification_spec(
            MUSHROOM_FEATURES, MUSHROOM_TARGET, threshold=0.93, full_score=100.0
        ),
        dataset=mushroom_edible_dataset,
    ),
    SeedProblem(
        slug="diabetes-screen",
        title="糖尿病篩檢 / Diabetes screening",
        statement_md=(
            "## 任務 / Task\n\n"
            "依葡萄糖、BMI、年齡、血壓、胰島素 5 個生理數值預測糖尿病 "
            "（`positive` / `negative`），準確率 ≥ 0.88。\n"
            "Binary diabetes screening from 5 clinical features. Target accuracy ≥ 0.88.\n\n"
            "### 參考解法 / Reference solution\n"
            "5 個特徵尺度差距明顯，建議 `Normalize(zscore)` → `LogisticRegression`。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["classification", "binary", "medical", "logistic-regression"],
        points=300,
        starter_template=_classification_template(
            train_path_default="data/samples/diabetes.csv",
            test_path_default="data/samples/diabetes_test.csv",
            target_column=DIABETES_TARGET,
            feature_columns=DIABETES_FEATURES,
            description="先標準化，再用 LogisticRegression 做糖尿病二元分類。",
        ),
        judge_spec=_classification_spec(
            DIABETES_FEATURES, DIABETES_TARGET, threshold=0.88, full_score=100.0
        ),
        dataset=diabetes_screen_dataset,
    ),
    SeedProblem(
        slug="fish-species",
        title="淡水魚種類 / Fish species classification",
        statement_md=(
            "## 任務 / Task\n\n"
            "依長度、重量、魚鰭比例分類 3 種淡水魚 `bream` / `perch` / `pike`，"
            "準確率 ≥ 0.92。\n"
            "Classify three freshwater fish species. Target accuracy ≥ 0.92.\n\n"
            "### 參考解法 / Reference solution\n"
            "重量和長度的數值差距很大，可以 `Normalize` 後 KNN，或直接用 KNN(k=3)。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["classification", "knn", "biology"],
        points=200,
        starter_template=_classification_template(
            train_path_default="data/samples/fish.csv",
            test_path_default="data/samples/fish_test.csv",
            target_column=FISH_TARGET,
            feature_columns=FISH_FEATURES,
            description="用 KNN 分類三種魚。",
        ),
        judge_spec=_classification_spec(
            FISH_FEATURES, FISH_TARGET, threshold=0.92, full_score=100.0
        ),
        dataset=fish_species_dataset,
    ),
    SeedProblem(
        slug="credit-approval",
        title="信用核准 / Credit approval",
        statement_md=(
            "## 任務 / Task\n\n"
            "用收入、負債比、信用歷史、在職年資、違約次數 5 個特徵預測 "
            "`approve` / `deny`，準確率 ≥ 0.88。\n"
            "Predict approve / deny from 5 credit features. Target accuracy ≥ 0.88.\n\n"
            "### 參考解法 / Reference solution\n"
            "強烈建議 `Normalize(zscore) → LogisticRegression`；SVMClassifier 也可。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["classification", "binary", "finance", "preprocessing"],
        points=300,
        starter_template=_classification_template(
            train_path_default="data/samples/credit.csv",
            test_path_default="data/samples/credit_test.csv",
            target_column=CREDIT_TARGET,
            feature_columns=CREDIT_FEATURES,
            description="先標準化再用 LogisticRegression 預測 approve / deny。",
        ),
        judge_spec=_classification_spec(
            CREDIT_FEATURES, CREDIT_TARGET, threshold=0.88, full_score=100.0
        ),
        dataset=credit_approval_dataset,
    ),
    SeedProblem(
        slug="student-pass",
        title="學生通過預測 / Student pass prediction",
        statement_md=(
            "## 任務 / Task\n\n"
            "從學習時數、出席率、先前成績、作業完成率預測學生 `pass` / `fail`，"
            "準確率 ≥ 0.92。\n"
            "Predict whether a student passes or fails from study habits. "
            "Target accuracy ≥ 0.92.\n\n"
            "### 參考解法 / Reference solution\n"
            "`LogisticRegression` 直接連即可；資料分得很開，無須標準化。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["classification", "binary", "education", "logistic-regression"],
        points=150,
        starter_template=_classification_template(
            train_path_default="data/samples/student.csv",
            test_path_default="data/samples/student_test.csv",
            target_column=STUDENT_TARGET,
            feature_columns=STUDENT_FEATURES,
            description="LogisticRegression 預測 pass / fail。",
        ),
        judge_spec=_classification_spec(
            STUDENT_FEATURES, STUDENT_TARGET, threshold=0.92, full_score=100.0
        ),
        dataset=student_pass_dataset,
    ),
    SeedProblem(
        slug="stellar-type",
        title="恆星類型分類 / Stellar type classification",
        statement_md=(
            "## 任務 / Task\n\n"
            "用亮度、log 溫度、質量、半徑 4 個天文特徵分類 3 類恆星："
            "`dwarf` / `main_sequence` / `giant`。準確率 ≥ 0.88。\n"
            "Classify three stellar types from astrophysical features. "
            "Target accuracy ≥ 0.88.\n\n"
            "### 參考解法 / Reference solution\n"
            "由於半徑可達 8 太陽單位、質量只有 0.3，建議先 `Normalize(zscore)` "
            "再用 `KNN(k=5)` 或 `SVMClassifier`。\n"
        ),
        difficulty=ProblemDifficulty.hard,
        tags=["classification", "knn", "astronomy", "preprocessing"],
        points=350,
        starter_template=_classification_template(
            train_path_default="data/samples/stellar.csv",
            test_path_default="data/samples/stellar_test.csv",
            target_column=STELLAR_TARGET,
            feature_columns=STELLAR_FEATURES,
            description="先 Normalize 再 KNN 對三類恆星分類。",
        ),
        judge_spec=_classification_spec(
            STELLAR_FEATURES, STELLAR_TARGET, threshold=0.88, full_score=100.0
        ),
        dataset=stellar_type_dataset,
    ),
    SeedProblem(
        slug="car-price",
        title="二手車估價 / Used car price regression",
        statement_md=(
            "## 任務 / Task\n\n"
            "依車齡、里程、排氣量、馬力預測二手車價（千元）。MSE ≤ 8.0 拿滿分。\n"
            "Predict used-car price from age / mileage / engine / horsepower. "
            "Full marks at MSE ≤ 8.0.\n\n"
            "### 參考解法 / Reference solution\n"
            "資料本身就是線性產生的，`LinearRegression` 直接即可；如想穩定就先 "
            "`Normalize`。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["regression", "linear-regression", "automotive"],
        points=300,
        starter_template=_regression_template(
            train_path_default="data/samples/car.csv",
            test_path_default="data/samples/car_test.csv",
            target_column=CARPRICE_TARGET,
            feature_columns=CARPRICE_FEATURES,
            description="LinearRegression 預測 price_k。",
        ),
        judge_spec=_regression_spec(
            CARPRICE_FEATURES, CARPRICE_TARGET, threshold=8.0, full_score=100.0
        ),
        dataset=car_price_dataset,
    ),
    SeedProblem(
        slug="salary-experience",
        title="薪資預測 / Salary regression",
        statement_md=(
            "## 任務 / Task\n\n"
            "依年資、學歷年數、證照數預測年薪（千元）。MSE ≤ 6.0 拿滿分。\n"
            "Predict salary (in k) from experience / education / certifications. "
            "Full marks at MSE ≤ 6.0.\n\n"
            "### 參考解法 / Reference solution\n"
            "`LinearRegression` 即可。三個特徵尺度接近，標準化非必要。\n"
        ),
        difficulty=ProblemDifficulty.easy,
        tags=["regression", "linear-regression"],
        points=200,
        starter_template=_regression_template(
            train_path_default="data/samples/salary.csv",
            test_path_default="data/samples/salary_test.csv",
            target_column=SALARY_TARGET,
            feature_columns=SALARY_FEATURES,
            description="LinearRegression 預測 salary_k。",
        ),
        judge_spec=_regression_spec(
            SALARY_FEATURES, SALARY_TARGET, threshold=6.0, full_score=100.0
        ),
        dataset=salary_experience_dataset,
    ),
    SeedProblem(
        slug="crop-yield",
        title="作物產量預測 / Crop yield regression",
        statement_md=(
            "## 任務 / Task\n\n"
            "依降雨、溫度、肥料、土壤評分預測單位作物產量（噸）。MSE ≤ 1.0 拿滿分。\n"
            "Predict crop yield in tons. Full marks at MSE ≤ 1.0.\n\n"
            "### 參考解法 / Reference solution\n"
            "`LinearRegression` 即可。資料是線性疊加的，無須非線性模型。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["regression", "linear-regression", "agriculture"],
        points=300,
        starter_template=_regression_template(
            train_path_default="data/samples/crop.csv",
            test_path_default="data/samples/crop_test.csv",
            target_column=CROP_TARGET,
            feature_columns=CROP_FEATURES,
            description="LinearRegression 預測 yield_tons。",
        ),
        judge_spec=_regression_spec(
            CROP_FEATURES, CROP_TARGET, threshold=1.0, full_score=100.0
        ),
        dataset=crop_yield_dataset,
    ),
    SeedProblem(
        slug="electricity-demand",
        title="用電量預測 / Electricity demand regression",
        statement_md=(
            "## 任務 / Task\n\n"
            "依小時、溫度、星期幾、是否假日預測用電量（MW）。MSE ≤ 12.0 拿滿分。\n"
            "Predict electricity demand in MW. Full marks at MSE ≤ 12.0.\n\n"
            "### 參考解法 / Reference solution\n"
            "建議 `Normalize` 後 `LinearRegression`，避免 hour (0–23) 與 "
            "is_holiday (0/1) 尺度差影響收斂。\n"
        ),
        difficulty=ProblemDifficulty.hard,
        tags=["regression", "linear-regression", "energy", "preprocessing"],
        points=350,
        starter_template=_regression_template(
            train_path_default="data/samples/electricity.csv",
            test_path_default="data/samples/electricity_test.csv",
            target_column=ELEC_TARGET,
            feature_columns=ELEC_FEATURES,
            description="先 Normalize 再用 LinearRegression 預測 demand_mw。",
        ),
        judge_spec=_regression_spec(
            ELEC_FEATURES, ELEC_TARGET, threshold=12.0, full_score=100.0
        ),
        dataset=electricity_demand_dataset,
    ),
    SeedProblem(
        slug="solar-output",
        title="太陽能輸出預測 / Solar output regression",
        statement_md=(
            "## 任務 / Task\n\n"
            "依日照強度、面板效率、氣溫、雲層覆蓋預測太陽能板每小時輸出（kWh）。"
            "MSE ≤ 1.2 拿滿分。\n"
            "Predict solar panel hourly output. Full marks at MSE ≤ 1.2.\n\n"
            "### 參考解法 / Reference solution\n"
            "`LinearRegression` 直接連即可，係數會自動覆蓋兩個尺度差較大的特徵。\n"
        ),
        difficulty=ProblemDifficulty.medium,
        tags=["regression", "linear-regression", "energy"],
        points=300,
        starter_template=_regression_template(
            train_path_default="data/samples/solar.csv",
            test_path_default="data/samples/solar_test.csv",
            target_column=SOLAR_TARGET,
            feature_columns=SOLAR_FEATURES,
            description="LinearRegression 預測 output_kwh。",
        ),
        judge_spec=_regression_spec(
            SOLAR_FEATURES, SOLAR_TARGET, threshold=1.2, full_score=100.0
        ),
        dataset=solar_output_dataset,
    ),
]


__all__ = ["SEED_PROBLEMS", "SeedProblem"]
