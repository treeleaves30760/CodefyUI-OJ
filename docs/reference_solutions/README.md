# Reference solutions

These `graph.json` files demonstrate one correct wiring per seeded problem.
They are written to be readable, not to be the *only* solution: any graph that
satisfies the judge spec (correct `required_node_ids`, predictions land on
`__SUBMIT__.value`) will be accepted.

## Common pattern

```
start ──trigger──▶ __TRAIN__ ──tensor──▶ model.x_train
                   __TRAIN__ ──labels──▶ model.y_train
start ──trigger──▶ __TEST_X__ ──tensor──▶ model.x_query
                                         model.predictions ──▶ __SUBMIT__.value
```

For problems with very different feature scales (Wine, Diabetes, Credit,
Stellar, Electricity) a `Normalize(zscore)` stage is inserted between the
readers and the model. The same `Normalize` is reused for both `x_train` and
`x_query` so train- and query-time statistics match.

## Mapping table

| Slug | Approach |
|---|---|
| warmup-passthrough | Direct passthrough: `__TRAIN__.labels → __SUBMIT__.value` |
| iris-knn | KNN(k=5) |
| wine-logistic | Normalize → LogisticRegression |
| customer-churn | Normalize → SVMClassifier (RBF) |
| housing-linear | LinearRegression |
| fruit-basket-knn | KNN(k=3) |
| coin-fairness | LogisticRegression |
| weather-rain-svm | Normalize → SVMClassifier (RBF) |
| seed-variety-knn | KNN(k=5) |
| mushroom-edible | KNN(k=5) |
| diabetes-screen | Normalize → LogisticRegression |
| fish-species | KNN(k=3) |
| credit-approval | Normalize → LogisticRegression |
| student-pass | LogisticRegression |
| stellar-type | Normalize → KNN(k=5) |
| car-price | LinearRegression |
| salary-experience | LinearRegression |
| crop-yield | LinearRegression |
| electricity-demand | Normalize → LinearRegression |
| solar-output | LinearRegression |
