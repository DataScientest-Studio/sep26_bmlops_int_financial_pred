<!-- Generated from requirements.sdoc by tools/export-requirements.sh. Do not edit. -->

# Financial forecasting service — requirements

## Objectives

1. Forecast the next trading day's price change of a configured security and offer the forecast through an API and an interactive app.
2. Keep the forecast current without manual steps: new quotes arrive, the model is retrained, a better model replaces the current one, and the running system is monitored for data drift and service health.
3. Compare every model honestly against simple baselines and state clearly that the service is not investment advice.

## Key metrics

Model quality, measured on data the model has not seen, ordered by time:

- Mean absolute error (MAE) of the predicted daily change.
- Skill against persistence: 1 − MAE(model) / MAE(persistence). Above 0 means the model beats "tomorrow's price equals today's" (predicted change 0); 0 or below is the expected result for daily prices and is reported as such.
- Directional accuracy: share of days on which the predicted sign of the change is correct.

Operation of the running system:

- Prediction latency (95th percentile) and error rate of the API.
- Data freshness: trading days between the latest stored quote and the latest available quote.
- Drift share: fraction of monitored features flagged as drifted in the latest check.
- Training runs: duration and outcome (succeeded, promoted, kept as candidate).

Threshold values for alerts, drift and model promotion are configuration, set by the team.

## How requirements are checked

Each requirement names how it is checked (VERIFICATION):

- Test: an automated black-box test calls the system through its public interfaces (API, commands, database) and names the requirement it checks.
- Demonstration: shown on the running system, because it depends on time passing or on a dashboard.
- Inspection: checked by review of the repository and its configuration; this covers the constraints set by the course.

Design choices and the schedule are not requirements; they are recorded in the plan and the decision documents.

## Data

### Historical load

**UID**: REQ-DAT-001 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system loads the complete daily price history (open, high, low, close, volume) of each configured security into its database in a single run.

### Daily ingestion

**UID**: REQ-DAT-002 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: The system adds the quotes of each new trading day to its database.

### Historical replay

**UID**: REQ-DAT-003 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: The system can replay stored history one trading day at a time, as if each day were arriving live, at a speed set by the operator.

**Rationale**: Shows the complete loop of ingestion, drift check, retraining and promotion within minutes instead of weeks.

### Trading calendar

**UID**: REQ-DAT-004 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system counts only trading days of the security's exchange; weekends, public holidays and trading suspensions are not treated as missing data.

### Quote validation

**UID**: REQ-DAT-005 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system rejects a quote with a missing field, a non-positive price or a duplicate trading day before it is stored, and records the rejection.

### Dataset versioning

**UID**: REQ-DAT-006 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: Every dataset used for training has a version identifier, and every trained model records the identifier of the dataset it was trained on.

## Model

### Forecast target

**UID**: REQ-MOD-001 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The model predicts the close-to-close change of a configured security from the latest trading day to the next trading day.

### Baselines

**UID**: REQ-MOD-002 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: Every evaluation also scores two baselines on the same data: persistence (tomorrow's price equals today's, i.e. a predicted change of 0) and the historical mean change.

### No look-ahead

**UID**: REQ-MOD-003 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: Features for a predicted day use only data dated before that day, and evaluation data is always later in time than training data.

### Experiment tracking

**UID**: REQ-MOD-004 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: Every training run records its parameters, metrics, dataset version and resulting model.

### Model promotion

**UID**: REQ-MOD-005 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: A newly trained model becomes the production model only if it scores better than the current production model on the same evaluation window; otherwise the current production model stays in place.

## Service

### Prediction endpoint

**UID**: REQ-SVC-001 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The API returns the production model's forecast for the next trading day of a requested security, together with the model version that produced it.

### Training endpoint

**UID**: REQ-SVC-002 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The API starts a training run on request and reports its outcome.

### Prediction log

**UID**: REQ-SVC-003 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: The system stores every prediction with its input features, model version and time of request.

### Access control

**UID**: REQ-SVC-004 \
**Status**: Draft \
**Tags**: phase-2, optional \
**VERIFICATION**: Test

**Statement**: The API answers only authenticated callers; starting a training and managing users are reserved for administrators.

## Automation

### Scheduled training pipeline

**UID**: REQ-AUT-001 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Demonstration

**Statement**: On a configured schedule, the system ingests new quotes, trains and evaluates a model, and applies the promotion rule, without manual steps.

### Outcome collection

**UID**: REQ-AUT-002 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: Once a predicted day's actual quote is stored, the system records it against each prediction for that day and computes the production error.

### One-command start

**UID**: REQ-AUT-003 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: The complete system starts with one command from a fresh clone of the repository, each component running as a separate service.

### Continuous integration

**UID**: REQ-AUT-004 \
**Status**: Draft \
**Tags**: phase-2, optional \
**VERIFICATION**: Inspection

**Statement**: Every push runs linting and unit tests and builds the service images; a push to the main branch also publishes the images.

## Monitoring

### Training data drift

**UID**: REQ-MON-001 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: Before training, the system compares recent data with historical reference data, records the drift report and metrics with the training run, and retrains when drift exceeds the configured threshold.

### Prediction input drift

**UID**: REQ-MON-002 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: On a configured schedule, the system compares logged prediction inputs with reference data, records the drift report and metrics, and starts the training pipeline when drift exceeds the configured threshold.

### Service metrics and dashboard

**UID**: REQ-MON-003 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Demonstration

**Statement**: The system collects request count, latency and error rate of the API and shows them, together with data freshness and the latest drift share, on a dashboard.

### Alerts

**UID**: REQ-MON-004 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: The system raises an alert when a monitored metric crosses its configured threshold; a configured alert starts the training pipeline.

## App

### Forecast view

**UID**: REQ-APP-001 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: The app lets a user choose a security and shows its recent price history, the model's forecast for the next trading day and the baseline forecasts.

### Not investment advice

**UID**: REQ-APP-002 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: Every page of the app states that the forecasts are not investment advice.

### Model results

**UID**: REQ-APP-003 \
**Status**: Draft \
**Tags**: phase-3 \
**VERIFICATION**: Test

**Statement**: The app shows the key model metrics of the production model next to those of the baselines.

## Course constraints

### Prescribed tools

**UID**: REQ-CON-001 \
**Status**: Draft \
**Tags**: course \
**VERIFICATION**: Inspection

**Statement**: The system uses the tools the course prescribes: MLflow for experiment tracking and the model registry, DVC without Git for dataset versions (hashes recorded in MLflow), Docker Compose for the services, Airflow for scheduled pipelines and drift checks, Evidently for drift reports, Prometheus and Grafana for service monitoring and alerts, Streamlit for the app, and an SQL or NoSQL database.

### Local operation

**UID**: REQ-CON-002 \
**Status**: Draft \
**Tags**: course \
**VERIFICATION**: Inspection

**Statement**: The complete system, including its database, runs on a local machine without any cloud service.

### Database as the data store

**UID**: REQ-CON-003 \
**Status**: Draft \
**Tags**: course \
**VERIFICATION**: Inspection

**Statement**: The system keeps all the data it uses in its database; files fetched from a data source are only read into the database, never used as storage.
