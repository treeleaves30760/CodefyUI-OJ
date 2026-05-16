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


__all__ = [
    "iris_like_dataset",
    "wine_like_dataset",
    "churn_like_dataset",
    "housing_like_dataset",
    "warmup_passthrough_dataset",
]
