# Model choice — which regressor

Decision: one model per security, a scikit-learn `StandardScaler` followed by
`LinearRegression`, predicting the next trading day's change from the 5 past daily
changes; listed in [`plan.md`, "Decisions"](../plan.md#decisions). The model is not
graded; the coach asks for at most 1–2 days of model work. The choice should make the
MLOps chain easy: fast training, a standard saved format, simple logging in MLflow.

## What the model has to do
- Predict the next trading day's close-to-close change of one security (a number), from
  features of its own price history: the daily changes of the last 5 trading days.
- Be compared on every run with the two baselines on the same evaluation days:
  persistence (predicted change 0) and the historical mean change. For daily prices, not
  beating them is the expected result.
- Retrain automatically and often (scheduled, after drift, after alerts), so training
  must be quick and need no hand tuning.
- Work with several securities: one model per security, or one shared model with the
  security as a feature.

## Criteria
- Training time and resources (retraining runs inside the pipeline, on a laptop).
- Risk of overfitting: daily price changes are mostly noise, and a flexible model finds
  patterns that are not there.
- Explainability at the defense: can we say in one sentence what the model does?
- MLflow support: logged and loaded with a built-in flavour (`mlflow.sklearn`), or extra
  work.
- Fit with the feature table and with one-model-per-security vs. one shared model.
- Extra packages in the environment and the images.

## Candidates

### Ridge regression (scikit-learn `Ridge`)
Linear regression with a penalty that keeps coefficients small.
- Pros: trains in milliseconds; stable on noisy, correlated features; each coefficient
  can be read and explained; logged with `mlflow.sklearn`; part of scikit-learn, no
  extra package.
- Cons: only straight-line relations between features and change; one setting to choose
  (the penalty strength).

### Linear regression (scikit-learn `LinearRegression`)
- Pros: the simplest model; no settings; each coefficient can be read and explained;
  logged with `mlflow.sklearn`; part of scikit-learn, no extra package.
- Cons: no penalty, so strongly correlated features would make the coefficients jump
  between runs (a small risk here: the 5 inputs are the changes of 5 different trading
  days, and daily changes are hardly correlated with each other); only straight-line
  relations between features and change.

### Lasso or ElasticNet (scikit-learn)
Linear regression whose penalty can set coefficients to exactly zero.
- Pros: picks features by itself; still fast and explainable.
- Cons: on mostly-noise data it often drops nearly every feature and falls back to the
  mean, which is the mean-change baseline; one or two more settings.

### Random forest (scikit-learn `RandomForestRegressor`)
- Pros: captures non-linear relations; little tuning; feature importances to show.
- Cons: slower and much larger saved models; fits the noise in daily data easily;
  predictions are averages of past values, so it cannot forecast outside the range it
  has seen.

### Gradient boosting (scikit-learn `HistGradientBoostingRegressor`, or LightGBM)
- Pros: the usual strongest choice for tabular data; captures non-linear relations; the
  scikit-learn version needs no extra package, LightGBM has its own MLflow flavour.
- Cons: many settings; easy to overfit daily data; harder to explain; LightGBM adds a
  package with compiled code to every image.

### AutoARIMA (Nixtla `statsforecast`, named in the subject)
Classic time-series model fitted to the change series of one security, choosing its own
order.
- Pros: the textbook forecasting model; no feature table; fast in `statsforecast`.
- Cons: one model per security by design; its own library, data format and saved format
  (logged in MLflow as a generic Python model); does not use the feature table the drift
  checks are built on.

### Up/down classification (logistic regression)
- Pros: simple to read; scored by accuracy.
- Cons: drops the size of the change, while the subject's target and both baselines are
  defined on the change itself.

## One model per security or one shared model
- Per security: each model sees one price series; more models to train, track and
  promote; fine for a handful of securities.
- Shared: one model trained on all securities, with the security as a feature; one
  registry entry, more training data; one bad security can skew the rest.
- Chosen: one model per security, the simplest fit for the model registry, which then
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
production model by the rule in [`plan.md`, "Better model"](../plan.md#better-model).
