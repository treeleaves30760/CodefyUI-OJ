"""Synthetic-dataset generators for seeded OJ problems.

Pure stdlib + deterministic seeding so the same CSVs land on every install
without bringing numpy/sklearn into the API image. Each generator returns
``(train_csv, test_features_csv, test_labels_csv)`` strings ready to be
written under ``storage/test_data/<slug>/``.
"""
from __future__ import annotations

import io
import math
import random


def _format_float(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


def _to_csv(headers: list[str], rows: list[list[object]]) -> str:
    buf = io.StringIO()
    buf.write(",".join(headers) + "\n")
    for row in rows:
        rendered = []
        for cell in row:
            if isinstance(cell, float):
                rendered.append(_format_float(cell))
            else:
                rendered.append(str(cell))
        buf.write(",".join(rendered) + "\n")
    return buf.getvalue()


def _gaussian_cluster(
    rng: random.Random,
    centers: list[float],
    spreads: list[float],
    n: int,
) -> list[list[float]]:
    rows: list[list[float]] = []
    for _ in range(n):
        rows.append(
            [rng.gauss(center, spread) for center, spread in zip(centers, spreads)]
        )
    return rows


def _classification_split(
    rng: random.Random,
    feature_headers: list[str],
    label_header: str,
    classes: list[tuple[str, list[float], list[float]]],
    n_train_per_class: int,
    n_test_per_class: int,
) -> tuple[str, str, str]:
    train_rows: list[list[object]] = []
    test_feature_rows: list[list[object]] = []
    test_label_rows: list[list[object]] = []

    for label, centers, spreads in classes:
        train = _gaussian_cluster(rng, centers, spreads, n_train_per_class)
        for sample in train:
            train_rows.append([*sample, label])
        test = _gaussian_cluster(rng, centers, spreads, n_test_per_class)
        for sample in test:
            test_feature_rows.append(list(sample))
            test_label_rows.append([label])

    rng.shuffle(train_rows)
    pairs = list(zip(test_feature_rows, test_label_rows))
    rng.shuffle(pairs)
    test_feature_rows = [p[0] for p in pairs]
    test_label_rows = [p[1] for p in pairs]

    train_csv = _to_csv([*feature_headers, label_header], train_rows)
    test_features_csv = _to_csv(feature_headers, test_feature_rows)
    test_labels_csv = _to_csv([label_header], test_label_rows)
    return train_csv, test_features_csv, test_labels_csv


def iris_like_dataset() -> tuple[str, str, str]:
    """Three-class flower classification, iris-shaped."""
    rng = random.Random(1)
    classes = [
        ("setosa",     [5.0, 3.4, 1.5, 0.2], [0.3, 0.3, 0.15, 0.08]),
        ("versicolor", [5.9, 2.8, 4.3, 1.3], [0.4, 0.3, 0.45, 0.20]),
        ("virginica",  [6.5, 3.0, 5.5, 2.0], [0.5, 0.3, 0.50, 0.25]),
    ]
    return _classification_split(
        rng,
        ["sepal_length", "sepal_width", "petal_length", "petal_width"],
        "species",
        classes,
        n_train_per_class=40,
        n_test_per_class=15,
    )


def wine_like_dataset() -> tuple[str, str, str]:
    """Three-cultivar wine classification — well-separated clusters."""
    rng = random.Random(2)
    classes = [
        ("cultivar_a", [13.5, 1.8, 2.3, 17.0, 105.0], [0.4, 0.5, 0.25, 2.0, 8.0]),
        ("cultivar_b", [12.4, 2.2, 2.1, 20.0,  95.0], [0.4, 0.7, 0.30, 2.5, 7.0]),
        ("cultivar_c", [13.1, 3.0, 2.5, 21.0,  98.0], [0.5, 0.9, 0.30, 2.5, 9.0]),
    ]
    return _classification_split(
        rng,
        ["alcohol", "malic_acid", "ash", "alcalinity", "magnesium"],
        "cultivar",
        classes,
        n_train_per_class=50,
        n_test_per_class=20,
    )


def churn_like_dataset() -> tuple[str, str, str]:
    """Binary customer-churn classification — modest class imbalance."""
    rng = random.Random(3)
    classes = [
        ("stay",  [4.5, 60.0, 0.9, 2.0,  3.0], [1.0, 15.0, 0.05, 1.0, 1.0]),
        ("churn", [1.5, 30.0, 0.4, 5.0, 12.0], [0.8, 12.0, 0.15, 2.0, 4.0]),
    ]
    return _classification_split(
        rng,
        ["tenure_years", "monthly_fee", "satisfaction", "support_calls", "missed_payments"],
        "churn_flag",
        classes,
        n_train_per_class=60,
        n_test_per_class=20,
    )


def housing_like_dataset() -> tuple[str, str, str]:
    """Linear regression target ~ true affine map + small noise."""
    rng = random.Random(4)
    coefs = [25.0, -1.2, 4.5, -0.8]
    intercept = 12.0
    headers = ["rooms", "age_years", "distance_metro_km", "crime_rate"]
    target_header = "price_k"

    train_rows: list[list[object]] = []
    test_feature_rows: list[list[object]] = []
    test_label_rows: list[list[object]] = []

    def synth_row() -> tuple[list[float], float]:
        x = [
            rng.uniform(2.0, 8.0),
            rng.uniform(1.0, 60.0),
            rng.uniform(0.2, 15.0),
            rng.uniform(0.0, 10.0),
        ]
        y = intercept + sum(c * v for c, v in zip(coefs, x)) + rng.gauss(0.0, 1.5)
        return x, y

    for _ in range(80):
        x, y = synth_row()
        train_rows.append([*x, y])
    for _ in range(25):
        x, y = synth_row()
        test_feature_rows.append(list(x))
        test_label_rows.append([y])

    rng.shuffle(train_rows)
    paired = list(zip(test_feature_rows, test_label_rows))
    rng.shuffle(paired)
    test_feature_rows = [p[0] for p in paired]
    test_label_rows = [p[1] for p in paired]

    return (
        _to_csv([*headers, target_header], train_rows),
        _to_csv(headers, test_feature_rows),
        _to_csv([target_header], test_label_rows),
    )


def warmup_passthrough_dataset() -> tuple[str, str, str]:
    """A one-shot dataset where the predictions == labels — pipeline warmup."""
    rng = random.Random(5)
    classes = [
        ("red",    [1.0, 0.1, 0.1], [0.05, 0.05, 0.05]),
        ("green",  [0.1, 1.0, 0.1], [0.05, 0.05, 0.05]),
        ("blue",   [0.1, 0.1, 1.0], [0.05, 0.05, 0.05]),
        ("yellow", [1.0, 1.0, 0.1], [0.05, 0.05, 0.05]),
    ]
    return _classification_split(
        rng,
        ["r", "g", "b"],
        "colour",
        classes,
        n_train_per_class=20,
        n_test_per_class=10,
    )


# -----------------------------------------------------------------------------
# Extended seed dataset library
#
# Each generator below uses a unique random seed so re-runs produce identical
# CSVs, and class centers are spaced far enough apart that the suggested model
# (KNN / LogisticRegression / SVM / LinearRegression) clears the threshold.
# Regression targets are produced by ``coefficients · features + intercept +
# gaussian noise`` so a plain LinearRegression saturates the score.
# -----------------------------------------------------------------------------


def _linear_regression_dataset(
    *,
    seed: int,
    headers: list[str],
    target_header: str,
    coefs: list[float],
    intercept: float,
    feature_ranges: list[tuple[float, float]],
    noise_std: float,
    n_train: int,
    n_test: int,
) -> tuple[str, str, str]:
    rng = random.Random(seed)
    train_rows: list[list[object]] = []
    test_feature_rows: list[list[object]] = []
    test_label_rows: list[list[object]] = []

    def synth_row() -> tuple[list[float], float]:
        x = [rng.uniform(lo, hi) for lo, hi in feature_ranges]
        y = intercept + sum(c * v for c, v in zip(coefs, x)) + rng.gauss(0.0, noise_std)
        return x, y

    for _ in range(n_train):
        x, y = synth_row()
        train_rows.append([*x, y])
    for _ in range(n_test):
        x, y = synth_row()
        test_feature_rows.append(list(x))
        test_label_rows.append([y])

    rng.shuffle(train_rows)
    paired = list(zip(test_feature_rows, test_label_rows))
    rng.shuffle(paired)
    test_feature_rows = [p[0] for p in paired]
    test_label_rows = [p[1] for p in paired]

    return (
        _to_csv([*headers, target_header], train_rows),
        _to_csv(headers, test_feature_rows),
        _to_csv([target_header], test_label_rows),
    )


# --- Classification (extra) --------------------------------------------------


def fruit_basket_dataset() -> tuple[str, str, str]:
    """3-class fruit identification — apples, oranges, bananas."""
    rng = random.Random(10)
    classes = [
        ("apple",  [160.0, 0.85, 0.20], [10.0, 0.05, 0.04]),
        ("orange", [200.0, 0.50, 0.75], [15.0, 0.07, 0.05]),
        ("banana", [120.0, 0.15, 0.90], [12.0, 0.05, 0.04]),
    ]
    return _classification_split(
        rng,
        ["weight_g", "red_score", "yellow_score"],
        "fruit",
        classes,
        n_train_per_class=40,
        n_test_per_class=15,
    )


def coin_balance_dataset() -> tuple[str, str, str]:
    """Binary fair / biased coin from session stats."""
    rng = random.Random(11)
    classes = [
        ("fair",   [0.50, 0.50, 4.0], [0.04, 0.04, 1.2]),
        ("biased", [0.78, 0.22, 9.0], [0.05, 0.05, 2.0]),
    ]
    return _classification_split(
        rng,
        ["heads_ratio", "tails_ratio", "max_streak"],
        "coin_type",
        classes,
        n_train_per_class=60,
        n_test_per_class=20,
    )


def weather_rain_dataset() -> tuple[str, str, str]:
    """Binary rain / no-rain prediction from a few weather sensors."""
    rng = random.Random(12)
    classes = [
        ("dry",  [28.0, 45.0, 1018.0], [3.5, 7.0, 3.0]),
        ("rain", [19.0, 86.0, 1003.0], [3.0, 5.5, 3.5]),
    ]
    return _classification_split(
        rng,
        ["temperature_c", "humidity_pct", "pressure_hpa"],
        "weather",
        classes,
        n_train_per_class=60,
        n_test_per_class=20,
    )


def seed_variety_dataset() -> tuple[str, str, str]:
    """3-class seed kernel classification (Kama / Rosa / Canadian-like)."""
    rng = random.Random(13)
    classes = [
        ("kama",     [14.5, 14.2, 15.1, 0.88], [0.6, 0.4, 0.5, 0.02]),
        ("rosa",     [18.0, 16.0, 18.5, 0.91], [0.8, 0.5, 0.6, 0.02]),
        ("canadian", [11.8, 13.0, 12.8, 0.84], [0.5, 0.4, 0.4, 0.02]),
    ]
    return _classification_split(
        rng,
        ["length", "width", "perimeter", "compactness"],
        "variety",
        classes,
        n_train_per_class=50,
        n_test_per_class=20,
    )


def mushroom_edible_dataset() -> tuple[str, str, str]:
    """Binary mushroom edibility — well separated clusters so KNN works."""
    rng = random.Random(14)
    classes = [
        ("edible",    [6.0, 8.0, 0.15, 0.20], [1.2, 1.5, 0.05, 0.07]),
        ("poisonous", [9.5, 4.5, 0.80, 0.85], [1.5, 1.4, 0.07, 0.08]),
    ]
    return _classification_split(
        rng,
        ["cap_cm", "stem_cm", "gill_dark_score", "odor_pungent_score"],
        "edible_flag",
        classes,
        n_train_per_class=70,
        n_test_per_class=25,
    )


def diabetes_screen_dataset() -> tuple[str, str, str]:
    """Binary diabetes screening from glucose / BMI / age / BP / insulin."""
    rng = random.Random(15)
    classes = [
        ("negative", [95.0,  24.0, 32.0,  75.0, 80.0],  [12.0, 2.5, 8.0, 7.0, 18.0]),
        ("positive", [165.0, 33.0, 47.0,  92.0, 165.0], [18.0, 3.5, 9.0, 9.0, 30.0]),
    ]
    return _classification_split(
        rng,
        ["glucose", "bmi", "age", "blood_pressure", "insulin"],
        "diabetes_label",
        classes,
        n_train_per_class=70,
        n_test_per_class=25,
    )


def fish_species_dataset() -> tuple[str, str, str]:
    """3-class freshwater fish species by length / weight / fin ratio."""
    rng = random.Random(16)
    classes = [
        ("bream",  [32.0, 700.0, 0.40], [3.0, 90.0, 0.03]),
        ("perch",  [22.0, 250.0, 0.55], [2.5, 50.0, 0.04]),
        ("pike",   [55.0, 1100.0, 0.30], [4.0, 150.0, 0.03]),
    ]
    return _classification_split(
        rng,
        ["length_cm", "weight_g", "fin_ratio"],
        "species",
        classes,
        n_train_per_class=40,
        n_test_per_class=15,
    )


def credit_approval_dataset() -> tuple[str, str, str]:
    """Binary credit-approval — moderately overlapping clusters."""
    rng = random.Random(17)
    classes = [
        ("approve", [85.0, 0.20, 6.5, 5.5, 0.3], [18.0, 0.07, 2.0, 2.0, 0.6]),
        ("deny",    [40.0, 0.55, 1.8, 1.2, 2.4], [12.0, 0.10, 1.2, 0.9, 0.9]),
    ]
    return _classification_split(
        rng,
        ["income_k", "debt_ratio", "credit_history_years", "employed_years", "defaults"],
        "decision",
        classes,
        n_train_per_class=70,
        n_test_per_class=25,
    )


def student_pass_dataset() -> tuple[str, str, str]:
    """Binary pass / fail from study habits and prior performance."""
    rng = random.Random(18)
    classes = [
        ("fail", [3.5, 60.0, 55.0, 0.45], [1.5, 12.0, 9.0, 0.15]),
        ("pass", [9.0, 92.0, 82.0, 0.92], [2.0, 5.0, 8.0, 0.05]),
    ]
    return _classification_split(
        rng,
        ["study_hours_per_week", "attendance_pct", "prev_grade", "assignments_done_ratio"],
        "result",
        classes,
        n_train_per_class=60,
        n_test_per_class=20,
    )


def stellar_type_dataset() -> tuple[str, str, str]:
    """3-class stellar classification (dwarf / main / giant)."""
    rng = random.Random(19)
    classes = [
        ("dwarf",          [0.30, 3.5,  0.30, 0.40], [0.10, 0.6, 0.08, 0.10]),
        ("main_sequence",  [1.00, 5.7,  1.05, 1.00], [0.15, 0.5, 0.12, 0.10]),
        ("giant",          [2.20, 4.2,  3.50, 8.50], [0.30, 0.5, 0.40, 1.20]),
    ]
    return _classification_split(
        rng,
        ["brightness_norm", "log_temperature", "mass_solar", "radius_solar"],
        "stellar_type",
        classes,
        n_train_per_class=40,
        n_test_per_class=15,
    )


# --- Regression (extra) ------------------------------------------------------


def car_price_dataset() -> tuple[str, str, str]:
    return _linear_regression_dataset(
        seed=20,
        headers=["age_years", "mileage_km10k", "engine_l", "horsepower"],
        target_header="price_k",
        coefs=[-1.2, -0.9, 4.5, 0.20],
        intercept=22.0,
        feature_ranges=[(0.0, 12.0), (0.5, 18.0), (1.0, 4.5), (60.0, 320.0)],
        noise_std=1.2,
        n_train=90,
        n_test=30,
    )


def salary_experience_dataset() -> tuple[str, str, str]:
    return _linear_regression_dataset(
        seed=21,
        headers=["years_experience", "education_years", "certifications"],
        target_header="salary_k",
        coefs=[3.2, 2.4, 1.5],
        intercept=18.0,
        feature_ranges=[(0.0, 25.0), (10.0, 22.0), (0.0, 8.0)],
        noise_std=2.0,
        n_train=80,
        n_test=30,
    )


def crop_yield_dataset() -> tuple[str, str, str]:
    return _linear_regression_dataset(
        seed=22,
        headers=["rainfall_mm", "avg_temp_c", "fertilizer_kg", "soil_quality"],
        target_header="yield_tons",
        coefs=[0.015, 0.30, 0.08, 1.10],
        intercept=2.0,
        feature_ranges=[(150.0, 900.0), (12.0, 32.0), (10.0, 120.0), (0.0, 10.0)],
        noise_std=0.6,
        n_train=80,
        n_test=30,
    )


def electricity_demand_dataset() -> tuple[str, str, str]:
    return _linear_regression_dataset(
        seed=23,
        headers=["hour", "temperature_c", "day_of_week", "is_holiday"],
        target_header="demand_mw",
        coefs=[1.2, 2.1, 0.5, -3.5],
        intercept=120.0,
        feature_ranges=[(0.0, 23.0), (-5.0, 35.0), (0.0, 6.0), (0.0, 1.0)],
        noise_std=2.5,
        n_train=100,
        n_test=30,
    )


def solar_output_dataset() -> tuple[str, str, str]:
    return _linear_regression_dataset(
        seed=24,
        headers=["sunlight_kwm2", "panel_efficiency", "temperature_c", "cloud_cover"],
        target_header="output_kwh",
        coefs=[35.0, 22.0, -0.25, -8.5],
        intercept=4.0,
        feature_ranges=[(0.2, 1.0), (0.10, 0.25), (5.0, 40.0), (0.0, 1.0)],
        noise_std=0.8,
        n_train=80,
        n_test=30,
    )


__all__ = [
    "iris_like_dataset",
    "wine_like_dataset",
    "churn_like_dataset",
    "housing_like_dataset",
    "warmup_passthrough_dataset",
    "fruit_basket_dataset",
    "coin_balance_dataset",
    "weather_rain_dataset",
    "seed_variety_dataset",
    "mushroom_edible_dataset",
    "diabetes_screen_dataset",
    "fish_species_dataset",
    "credit_approval_dataset",
    "student_pass_dataset",
    "stellar_type_dataset",
    "car_price_dataset",
    "salary_experience_dataset",
    "crop_yield_dataset",
    "electricity_demand_dataset",
    "solar_output_dataset",
]
