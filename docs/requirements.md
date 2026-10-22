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

## What the product supports

- One local machine per team member, running the whole system with Docker Compose; no cloud service and no machine shared between members.
- Python 3.12, with the environment managed by uv.
- Docker Engine 28.0 or later (Docker Desktop includes it).
- Market data from EODHD with the member's own key; the reference securities (six stocks, two market indices) fit the free tier's 20 calls per day with one load or update per day.
- Every service listens on the local machine only (127.0.0.1).
- The scheduled pipeline runs either the daily update or replay, one at a time.
- At most one load or replay runs at a time, scheduled or manual; a manual one runs only while the scheduled pipeline is paused.
- At most one training runs at a time, scheduled or manual; a manual one runs only while the scheduled pipeline is paused.
- A missed scheduled run is not repeated; the next daily update fetches from the latest stored day.
- Not guarded against: anyone or anything on the member's own machine — another account, program or web page; every service is published on 127.0.0.1 only, or not at all.

## Data

### Historical load

**UID**: REQ-DAT-001 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system loads the daily price history (open, high, low, close, volume) from a configured first day on of each configured security and market index, and each security's splits and dividends, into its database in a single run. Prices and volumes are stored as traded on each day, not adjusted for later splits or dividends.

### Daily ingestion

**UID**: REQ-DAT-002 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: The system adds the quotes of each new trading day to its database, fetching only the days from its latest stored quote on.

### Historical replay

**UID**: REQ-DAT-003 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: The system can replay stored history one trading day at a time, as if each day were arriving live, into a database of its own, at an interval set by the operator: one trading day every 10 to 60 seconds. The history it replays from stays unchanged.

**Rationale**: Shows the complete loop of ingestion, drift check, retraining and promotion within minutes instead of weeks.

### Trading calendar

**UID**: REQ-DAT-004 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system counts only trading days of the security's exchange; weekends, public holidays and trading suspensions are not treated as missing data.

### Validation of delivered data

**UID**: REQ-DAT-005 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system rejects a delivered quote, split or dividend with a missing field, a non-positive price, ratio or amount, or a day delivered twice in one delivery before it is stored, and records the rejection. It also rejects a quote with a negative volume or on a day that is not a trading day of its exchange.

### Dataset versioning

**UID**: REQ-DAT-006 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: Every dataset used for training has a version identifier, and every trained model records the identifier of the dataset it was trained on.

### Provisional closes

**UID**: REQ-DAT-007 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The system stores each quote with the time it was fetched. A quote fetched before a set delay after its exchange's close of that trading day is provisional and is replaced by a later fetch of the same day; a quote fetched after that is final and is never replaced.

**Rationale**: The data source delivers the current day while its session is still running, in the same form as a finished day.

## Model

### Forecast target

**UID**: REQ-MOD-001 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The model predicts the close-to-close change of a configured security from the latest trading day to the next trading day. It is trained on final closes only.

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

**Statement**: A newly trained model becomes the production model only if its mean absolute error on the configured evaluation window is lower than that of the current production model on the same days; otherwise, a tie included, the current production model stays in place. The first model trained for a security becomes its production model.

## Service

### Prediction endpoint

**UID**: REQ-SVC-001 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The API returns the production model's forecast for the next trading day of a requested security, together with the model version that produced it, the close the forecast starts from and the time that close was fetched. A symbol that is not a configured security is refused.

### Training endpoint

**UID**: REQ-SVC-002 \
**Status**: Draft \
**Tags**: phase-1 \
**VERIFICATION**: Test

**Statement**: The API starts a training run on request and reports its outcome. A symbol that is not a configured security is refused.

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

### Commands from any folder

**UID**: REQ-AUT-005 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Test

**Statement**: Each command of the system works the same whatever folder it is started from.

### One packaged environment

**UID**: REQ-AUT-006 \
**Status**: Draft \
**Tags**: phase-2 \
**VERIFICATION**: Inspection

**Statement**: The system's commands, and its services built from its own code, run in one packaged environment with the pinned package versions.

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

**Statement**: The system uses the tools the course prescribes: MLflow for experiment tracking and the model registry, DVC without Git for dataset versions (hashes recorded in MLflow), Docker Compose for the services, Airflow for scheduled pipelines and drift checks, Evidently for drift reports, Prometheus and Grafana for service monitoring and alerts, and an SQL or NoSQL database.

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

**Statement**: The system keeps all the data it uses in its database; files fetched from a data source are only read into the database, never used as storage. DVC snapshots are version records of training datasets, never a store that data is read from.
