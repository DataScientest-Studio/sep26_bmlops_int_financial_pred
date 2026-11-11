# Model choice — which regressor

Decision: one model per security, a scikit-learn `StandardScaler` followed by
`LinearRegression`, predicting the next trading day's change from the 5 past daily
changes; listed in [`plan.md`, "Decisions"]. The model is not graded; the coach asks for
at most 1–2 days of model work. The choice should make the MLOps chain easy: fast
training, a standard saved format, simple logging in MLflow.

[`plan.md`, "Decisions"]: ../plan.md#decisions

## What the model has to do

-   Predict the next trading day's close-to-close change of one security (a number),
    from features of its own price history: the daily changes of the last 5 trading
    days.
-   Be compared on every run with the two baselines on the same evaluation days:
    persistence (predicted change 0) and the historical mean change. For daily prices,
    not beating them is the expected result.
-   Retrain automatically and often (scheduled, after drift, after alerts), so training
    must be quick and need no hand tuning.
-   Work with several securities: one model per security, or one shared model with the
    security as a feature.

## Criteria

-   Training time and resources (retraining runs inside the pipeline, on a laptop).
-   Risk of overfitting: daily price changes are mostly noise, and a flexible model
    finds patterns that are not there.
-   Explainability at the defense: can we say in one sentence what the model does?
-   MLflow support: logged and loaded with a built-in flavour (`mlflow.sklearn`), or
    extra work.
-   Fit with the feature table and with one-model-per-security vs. one shared model.
-   Extra packages in the environment and the images.

## Candidates

### Ridge regression (scikit-learn `Ridge`)

Linear regression with a penalty that keeps coefficients small.

Pros:

-   Trains in milliseconds.
-   Stable on noisy, correlated features.
-   Each coefficient can be read and explained.
-   Logged with `mlflow.sklearn`.
-   Part of scikit-learn, no extra package.

Cons:

-   Only straight-line relations between features and change.
-   One setting to choose (the penalty strength).

### Linear regression (scikit-learn `LinearRegression`)

Pros:

-   The simplest model.
-   No settings.
-   Each coefficient can be read and explained.
-   Logged with `mlflow.sklearn`.
-   Part of scikit-learn, no extra package.

Cons:

-   No penalty, so strongly correlated features would make the coefficients jump between
    runs (a small risk here: the 5 inputs are the changes of 5 different trading days,
    and daily changes are hardly correlated with each other).
-   Only straight-line relations between features and change.

### Lasso or ElasticNet (scikit-learn)

Linear regression whose penalty can set coefficients to exactly zero.

Pros:

-   Picks features by itself.
-   Still fast and explainable.

Cons:

-   On mostly-noise data it often drops nearly every feature and falls back to the mean,
    which is the mean-change baseline.
-   One or two more settings.

### Random forest (scikit-learn `RandomForestRegressor`)

Pros:

-   Captures non-linear relations.
-   Little tuning.
-   Feature importances to show.

Cons:

-   Slower and much larger saved models.
-   Fits the noise in daily data easily.
-   Predictions are averages of past values, so it cannot forecast outside the range it
    has seen.

### Gradient boosting (scikit-learn `HistGradientBoostingRegressor`, or LightGBM)

Pros:

-   The usual strongest choice for tabular data.
-   Captures non-linear relations.
-   The scikit-learn version needs no extra package, LightGBM has its own MLflow
    flavour.

Cons:

-   Many settings.
-   Easy to overfit daily data.
-   Harder to explain.
-   LightGBM adds a package with compiled code to every image.

### AutoARIMA (Nixtla `statsforecast`, named in the subject)

Classic time-series model fitted to the change series of one security, choosing its own
order.

Pros:

-   The textbook forecasting model.
-   No feature table.
-   Fast in `statsforecast`.

Cons:

-   One model per security by design.
-   Its own library, data format and saved format (logged in MLflow as a generic Python
    model).
-   Does not use the feature table the drift checks are built on.

### Up/down classification (logistic regression)

Pros:

-   Simple to read.
-   Scored by accuracy.

Cons:

-   Drops the size of the change, while the subject's target and both baselines are
    defined on the change itself.

## One model per security or one shared model

-   Per security: each model sees one price series; more models to train, track and
    promote; fine for a handful of securities.
-   Shared: one model trained on all securities, with the security as a feature; one
    registry entry, more training data; one bad security can skew the rest.
-   Chosen: one model per security, the simplest fit for the model registry, which then
    holds one registered model per security. Revisit if the list of securities grows
    (scope level 2).

## Decision

Each security gets its own model: `StandardScaler` followed by `LinearRegression`, saved
as one scikit-learn pipeline with `mlflow.sklearn`. It is the simplest candidate: it has
no settings, retrains quickly, and each coefficient can be explained at the defense. The
scaler brings every input to mean 0 and standard deviation 1. That leaves the linear
regression's predictions unchanged, but Ridge's penalty depends on the scale of the
inputs, so with the scaler in place a switch to Ridge is a one-word change.

The other candidates were weighed and not chosen. Each new model competes with the
production model by the rule in [`ARCHITECTURE.md`, "Better model"].

[`ARCHITECTURE.md`, "Better model"]: ../../ARCHITECTURE.md#better-model
