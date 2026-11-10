# Financial forecasting service

Forecasts the next trading day's price change of a security and offers the forecast
through an API. Automated pipelines keep it current: new quotes are loaded, a model is
trained for each security, and a better model replaces the current one. A dashboard
shows how the API is used and how up to date the prices are, and alerts fire when the
API returns server errors, the prices fall behind or a daily update is missed. A web app
shows the forecasts. A prediction drift check compares each security's recent forecasts
with the forecasts its production model makes for the days it was trained on. When they
differ, the model of every security is trained again.

**Not investment advice.** Short-term prices move close to randomly; every model is
compared with simple baselines ("tomorrow's price equals today's", and the historical
mean change), and beating them is not expected.

Group project of the DataScientest MLOps bootcamp (sep26 cohort).

## Status
Under construction. `make load` and `make update` load prices, splits and dividends from
EODHD, a provider of market data with a free tier. `make replay` replays stored history
one trading day at a time, as if each day were arriving live. Airflow, a tool that runs
chains of tasks (pipelines) at set times or when another pipeline announces new data,
runs both on a schedule (`make airflow`). The API reports numbers about its own use and
about how up to date the prices are; Grafana, a tool for dashboards and alerts, shows
them (`make monitoring`). Training and the forecast work as commands (`make train`,
`make predict`). Airflow also runs training when new or replayed prices arrive, and then
makes one scheduled forecast of each security: a forecast the training pipeline makes
and marks, so that the prediction drift check can use it. The web app shows a security's
forecast and the model's results (`make webapp`). Before training, the system tests
whether a security's recent daily price changes differ from those it was trained on.
This test, the feature drift check, is recorded in MLflow. After the scheduled
forecasts, Airflow asks the API to test whether the production model's recent forecasts
differ from its forecasts for the days it was trained on. This test, the prediction
drift check, is recorded in MLflow too; when it finds drift, every security is trained
again.

## Project structure
```
├── README.md
├── .github/workflows/
│   └── ci.yaml                  style check and unit tests on every push (GitHub Actions)
├── Makefile                     setup and maintenance commands
├── pyproject.toml               project metadata and packages
├── uv.lock                      exact versions of all packages, written by uv
├── .python-version              Python version
├── .gitignore                   files Git leaves out, among them .env, the Python environment, the datasets folder, price data (CSV) and caches
├── Dockerfile                   project image: the code with its locked packages, for the commands, the API, the data service and the MLflow server
├── .dockerignore                what the project image and the web app image are built from
├── compose.yaml                 services run in Docker: the PostgreSQL database, the object store, the MLflow server, the API, the web app, the data service, Airflow, Prometheus, Grafana, and the project commands on demand
├── .env.example                 template for the local .env (database login, Airflow, MLflow, web app and Grafana ports, Airflow and Grafana logins, object-store login, MLflow address for programs run on this machine outside Docker, first day of history, replay start and interval, EODHD key)
├── airflow/
│   └── dags/
│       ├── daily_update.py      the daily update pipeline: one load on the days and at the time config/daily_update.toml sets
│       ├── prediction_drift_check.py  the prediction drift check pipeline: runs after the scheduled forecasts, asks the API to check each configured security for prediction drift, and announces drift when any check finds it; a check that ends in an error does not stop the others, and the run then fails, naming each such security
│       ├── replay.py            the replay pipeline: one replayed trading day per interval
│       ├── service_call.py      the calls the pipelines make to the project's services: a single call, or one call for each security in config/securities.toml, which is read again at each run; a failed call gives the reason the service answered with, or the error reported when no answer came
│       └── training.py          the training pipeline: runs on new prices, replayed prices or prediction drift; after prediction drift it trains every configured security, otherwise only those the API finds due; then it makes one scheduled forecast of each; a failed training or forecast does not stop the others, and the run then fails, naming each such security
├── config/
│   ├── daily_update.toml        when the daily update loads, how long a load may run and when a fetched price is final
│   ├── drift_checks.toml        drift checks: drift window, check interval of the prediction drift check, drift p-value threshold
│   ├── securities.toml          securities to load, train and forecast; market indices to load as reference series
│   └── training.toml            training: evaluation days and retraining interval
├── db/
│   ├── init/
│   │   ├── dividends.sql        creates the dividends table where it is missing
│   │   ├── loads.sql            creates the loads table: each security's latest fetch time
│   │   ├── predictions.sql      creates the predictions table: one row per forecast, with whether it was scheduled
│   │   ├── prices.sql           creates the prices table where it is missing
│   │   └── splits.sql           creates the splits table where it is missing
│   ├── queries/
│   │   ├── examples.sql         example queries on the prices table
│   │   ├── sample-data.sql      made-up prices for trying them
│   │   └── remove-sample-data.sql  removes the made-up prices again
│   └── tools/
│       └── create-database.sql  creates a service's own database and login on the project's database server (Airflow, MLflow)
├── docs/
│   ├── requirements.sdoc        requirements source (StrictDoc)
│   ├── requirements.md          readable version, generated
│   ├── plan.md                  decisions, decision proposals, roadmap, phase plan, open points
│   ├── dependencies.md          every Python package and what it does
│   ├── team.md                  team setup: areas, meetings, communication, work tracking
│   └── decisions/
│       ├── database.md          PostgreSQL or NoSQL
│       ├── password-hashing.md  how user passwords are stored
│       ├── regressors.md        which model
│       └── trading-calendar.md  how trading days are known
├── grafana/
│   ├── dashboards/
│   │   └── api.json             the dashboard "API" (Grafana reads it at start)
│   └── provisioning/
│       ├── alerting/
│       │   └── alerts.yaml      the alert rules "API error rate", "Data not fresh" and "Daily update missed"
│       ├── dashboards/          where Grafana finds the dashboards
│       └── datasources/         Grafana's data source (Prometheus)
├── prometheus/
│   ├── prometheus.yml           what Prometheus collects, from where and how often
│   └── rules.yml                the error rate Prometheus computes and stores
├── references/                  course brief, condensed
│   ├── README.md                index, sources and their precedence
│   ├── subject.md               prediction task, scope levels, data sources
│   ├── schedule.md              phases, deadlines, defense
│   ├── course-checklist.md      what to build, per phase
│   ├── architecture.md          reference pipelines, components, tools
│   └── evaluation.md            what is graded, defense format
├── datasets/                    copies of the training datasets with their version records, kept by DVC (gitignored)
├── webapp/                      the web app
│   ├── app.py                   the page: a security's closes, forecasts and model results, read through the API
│   ├── Dockerfile               web app image: the webapp group's packages (Streamlit, the HTTP client, pandas), without the service's code (src/forecasting/)
│   └── .streamlit/
│       └── config.toml          Streamlit's settings inside the container
├── src/forecasting/             the service
│   ├── commands.py              commands the Makefile runs (load, replay, replay-reset, train, predict); the data service runs the same load and replay
│   ├── data_service.py          the data service: runs the load and the replay for the scheduled pipelines
│   ├── failures.py              the answer the API and the data service give when a request fails unexpectedly
│   ├── config.py                settings from .env and config/
│   ├── db.py                    database connection, reading prices and scheduled forecasts, creating and dropping databases
│   ├── datasets.py              version ids of the training datasets, recorded with DVC
│   ├── trading_calendar.py      trading days of each exchange
│   ├── load.py                  loading prices, splits and dividends from a data source
│   ├── eodhd.py                 the EODHD data source
│   ├── replay.py                replay of stored history into a database of its own, which training and forecasts use while it exists, and so do the API's price history and model results, deleting it with the replay runs and models
│   ├── features.py              model inputs and target
│   ├── train.py                 training of one security's model
│   ├── evaluate.py              scores of model and baselines
│   ├── predict.py               forecasts, the prediction drift check, recent closes and production model results
│   ├── drift_checks.py          drift checks, each recorded as its own run in MLflow
│   └── api/                     FastAPI app, endpoints, request and response bodies, the numbers at /metrics
├── tests/
│   ├── acceptance/              black-box tests, one or more per testable requirement
│   ├── contract/                checks of how EODHD delivers data, run with your own key
│   ├── integration/             tests of our code against the real database
│   ├── unit/                    tests of single functions and the wiring of the API and the data service
│   ├── conftest.py              shared fixtures: a test database per worker, API client
│   └── fakes.py                 stand-in data source with generated prices
└── tools/
    ├── export-requirements.sh   regenerates docs/requirements.md
    └── run-as-owner.sh          starts the project image's commands, API and data service as the owner of datasets/
```

## Setup
Needs [uv](https://docs.astral.sh/uv/), `make` and Docker with Compose. From a fresh
clone:

```bash
cp .env.example .env      # then add your own EODHD key (see "EODHD key" below); keep the development login
make setup                # Python environment in .venv/
make db                   # starts PostgreSQL, waits until it is ready
make load                 # builds the project image, loads the price history from EODHD
```

After that, `make update` once a day adds the new trading days.

`.env` needs every setting of `.env.example`; a missing one is named when a command, the
API or the data service starts.

`make setup` installs the Python version from `.python-version` if missing and creates
`.venv/` with the packages pinned in `uv.lock`; tests and checks run from it.

`make db` starts the database on `localhost`, at the port set in `.env`. Its data lives
in a Docker volume and survives restarts. The tables `prices`, `splits`, `dividends`,
`loads` and `predictions` are created on the first start. The Compose service
`db-tables` runs the scripts in `db/init/` again at each start of the services; they
only create the tables a database lacks, so the member's own database gains a table
added to `db/init/` without a reload. The replay database (see "Replay" below) gains it
only once `make replay-reset` deletes the replay database and the next `make replay`
creates it again. A change to a table that already exists takes effect only after the
database is deleted and created again: `make reset` (see the table below) deletes the
stored data, and the next `make` command that starts the database creates every table
from `db/init/`.

`make load`, `make update`, `make replay`, `make replay-reset`, `make train`,
`make predict` and `make api` run in the project image (`Dockerfile`), with the packages
pinned in `uv.lock` and the settings of `.env`. Each rebuilds the image when the code
changed and starts the database, the object store and the MLflow server first if they
are not running. Trained models are recorded in MLflow (see
[Model tracking](#model-tracking)). Copies of the training datasets are kept in
`datasets/` of the project folder and never committed; the containers run as the owner
of that folder, so the files belong to you. `docker compose logs api` shows the API's
output, errors included.

| Command | Effect |
|---|---|
| `make db` | start the database |
| `make db-stop` | stop it; the data is kept |
| `make db-shell` | SQL prompt in the database |
| `make load`, `make update` | load prices, splits and dividends from EODHD with your key: a security without stored prices from `HISTORY_START` on, otherwise only its new days; prints how many quotes were stored, replaced, rejected and missing |
| `make replay` | copy the next stored day from the database into the replay database; prints the day replayed (see "Replay" below) |
| `make replay-reset` | delete the replay database and the replay runs and models in MLflow, and remove for good whatever was deleted on the MLflow page; training, forecasts and the API's price history and model results return to the member's own database and models, and the next `make replay` starts over from `REPLAY_START` |
| `make reset` | stop every service and delete everything stored, for good: the database with the prices, the forecasts and the records of MLflow and Airflow, the object store, the pipeline logs, the monitoring history and the copies in `datasets/`; the next `make` command that starts the database creates every table from `db/init/`, and `make update` loads the history again; needed after a change to a table that already exists |
| `make train` | train a model for each configured security on its final closes, holding back the latest days (`evaluation_days` in `config/training.toml`) for scoring; first, for a security that already has a recorded training, records a feature drift check in MLflow; records the run and registers the model in MLflow; promotes it to production if it is the security's first or has a lower error than the production model on the same latest days (the production model is scored again on those days); prints its scores next to both baselines and whether it was promoted or production was kept |
| `make predict` | print the production model's forecast of the next trading day for each configured security and store each forecast in the table `predictions`, as the API's `/predict` does |
| `make lint` | code style, formatting and type check (ruff, pyright); changes no files |
| `make test` | unit tests; needs no database |
| `make acceptance` | start the database, then run the black-box tests of the requirements and the integration tests against the database; the passed count shows progress |
| `make contract` | checks how EODHD delivers data, with your own key from `.env`; a check your key's history, remaining calls or plan cannot support is skipped with its reason |
| `make api` | start the API on http://localhost:8000, documentation at `/docs`; returns once it answers |
| `make api-stop` | stop the API |
| `make webapp` | start the web app and the API it calls; its page is on `localhost` at the port `WEBAPP_PORT` from `.env` (see "Web app" below); returns once both answer |
| `make webapp-stop` | stop the web app; the API keeps running |
| `make mlflow` | start the MLflow server with the database and the object store; its page is on `localhost` at the port `MLFLOW_PORT` from `.env` (see "Model tracking" below); returns once it answers |
| `make mlflow-stop` | stop the MLflow server and the object store; the database keeps running |
| `make airflow` | start Airflow with the database, the data service and the API; its page is on `localhost` at the port `AIRFLOW_PORT` from `.env` (see "Scheduled pipelines" below); returns once it answers |
| `make airflow-stop` | stop Airflow and the data service; the database and the API keep running |
| `make monitoring` | start Prometheus and Grafana with the API; the Grafana page is on `localhost` at the port `GRAFANA_PORT` from `.env` (see "Monitoring" below); returns once it answers |
| `make monitoring-stop` | stop Prometheus and Grafana; the API keeps running |

The tests log in with the database values of `.env.example`, while `make db` uses those
of your `.env`, so keep the same `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and
`POSTGRES_PORT` in `.env`; a test that cannot log in stops with "Cannot log in to the
database with the values of .env.example; start it with make db and keep those values in
.env".

`make db-shell` opens an SQL prompt (`\q` leaves it). For example, the latest day stored
per security:

```sql
SELECT symbol, max(day) AS latest_day, count(*) AS days
FROM prices
GROUP BY symbol;
```

More examples are in `db/queries/examples.sql`. Run a file with:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/queries/examples.sql
```

To try the examples before real prices are loaded, run `db/queries/sample-data.sql` the
same way. It adds made-up prices under the symbols `AAPL.SAMPLE` and `SAP.SAMPLE`; the
suffix keeps them apart from real prices, which are stored as `AAPL.US` and `SAP.XETRA`.
`db/queries/remove-sample-data.sql` removes them again:

```sql
DELETE FROM prices WHERE symbol LIKE '%.SAMPLE';
```

`LIKE '%.SAMPLE'` matches every symbol that ends in `.SAMPLE` (`%` stands for any text),
so real prices are never deleted.

### Replay
Replay plays stored history back one trading day at a time, as if each day were arriving
live, so the pipeline can be shown over weeks of data within minutes. It copies prices,
splits and dividends from the database into a database of its own on the same server,
named after it with `_replay` (`forecasting_replay` for `forecasting`), and only reads
the database it copies from; it makes no EODHD calls. The first `make replay` creates
the replay database and fills it with every stored day up to `REPLAY_START`, which must
lie between the first and the latest stored day. Each later run copies the replay
database's latest day again, so a price that has become final since replaces the
provisional one, and then the next stored day. Each run copies all or nothing. Once the
latest stored day is copied, nothing is left to replay. While the replay database
exists, training, forecasts (`make train` and `make predict` included) and the
prediction drift check use it instead of the database it copies from, and so do the
API's price history and model results (the production model's scores next to the
baselines'). Training keeps the replay runs and models apart from the member's own in
MLflow: runs in the experiments `replay-forecasting` and `replay-drift-checks`, models
as `replay-forecast-<symbol>`. Forecasts, model results and the prediction drift check
use those replay models, so during a replay the model results are those of the replay's
production model. Forecasts are stored in the replay database. `make replay-reset`
deletes the replay database with its forecasts, and these runs and models, model files
included, to start over. It also removes for good whatever was deleted on the MLflow
page, and it returns training, forecasts and the API's price history and model results
to the member's own database and models.

### Web app
The web app is the page for looking at the forecasts. `make webapp` starts it together
with the API it calls and returns once both answer; its page is on `localhost` at the
port `WEBAPP_PORT` from `.env`, and only this machine reaches it. `make webapp-stop`
stops the web app and leaves the API running.

The page opens with the notice that the forecasts are not investment advice. Choose one
of the configured securities the API lists and the page shows:

- a chart of the security's closes over its latest 60 trading days;
- the forecast of the next trading day, with the day it is for, the close it starts from
  and the model version. It gives the change and the close the model forecasts, next to
  those of both baselines:
  - persistence, which forecasts no change;
  - the mean change of the model's training days, only if the training run recorded it;
- the production model's scores on the evaluation days of its training run, next to the
  baselines' scores: MAE (mean absolute error: the average size of a forecast's miss),
  skill against persistence (how much smaller the model's MAE is than persistence's;
  above 0 beats it) and directional accuracy (the share of days with the right direction
  of change).

The web app reads everything through the API and touches neither the database nor
MLflow. For a security without a production model, the page shows the API's reason for
giving no forecast. When the API fails on a request, the page shows the API's reason
instead of the forecasts. While the replay database exists, the closes, the forecast and
the model results are those of the replay (see [Replay](#replay)).

The API stores every forecast it makes, so the web app asks for a security's forecast
once per latest close and production model. It asks again after a new trading day, when
a final close replaces a provisional one or when a new model is promoted. Clicking does
not.

### Scheduled pipelines
Airflow runs the pipelines on a schedule. `make airflow` starts it; its page is on
`localhost` at the port `AIRFLOW_PORT` from `.env`. Log in as `admin` with the password
`AIRFLOW_ADMIN_PASSWORD` from `.env`. Airflow keeps its own database and login on the
project's database server, both created on the first start. Of the project's settings it
receives only `REPLAY_INTERVAL_SECONDS` from `.env` and the folder `config/`, which it
can read but not change; it never receives the EODHD key. Its tasks call two services,
both inside Docker: the data service, which runs loads and replays, and the API, which
runs training, forecasts and drift checks. The data service is not reachable from the
host; the API is, at `http://localhost:8000`.

The daily update pipeline (`daily_update`) runs one load on the days and at the time
that `config/daily_update.toml` sets, the same load as `make update`. Its settings are
in the table under [Monitoring settings](#monitoring-settings), since the API also uses
them to count missed daily updates. The final delay (`final_delay_minutes`), how long
after an exchange's close a fetched price counts as final, applies to every load, also
`make update`. A failed run is not repeated, since a load uses the free tier's calls of
the day; a run missed while Airflow was stopped is made up once if Airflow starts again
on the same day in the time zone set in `config/daily_update.toml` (`timezone`), and
skipped from the next day on; either way the next load fetches from the latest stored
day on.

The replay pipeline (`replay`) replays one trading day every `REPLAY_INTERVAL_SECONDS`
seconds, the same replay as `make replay` (see [Replay](#replay)). Airflow refuses to
load it while the interval lies outside its limits and names them on its page. A missed
run is not made up, and a run that is still going delays the next one. Once the latest
stored day is replayed, each run is skipped: switch the pipeline off and run
`make replay-reset`.

The pipelines announce their work, so that another pipeline can start on it. What they
announce is an asset, Airflow's word for a named marker that a task announces when it
succeeds and that pipelines wait for. A pipeline announces an asset through one of its
tasks, and a skipped or failed task announces nothing. The daily update pipeline
announces the asset `prices` after each load, also after one that found no new trading
day; the replay pipeline announces the asset `replay-prices` after each replayed day.
The training pipeline announces the asset `scheduled-forecasts` after its forecasts, and
the prediction drift check pipeline announces the asset `prediction-drift-found` when a
check finds drift. The page lists all four under "Assets".

The training pipeline (`training`) starts whenever one of the assets `prices`,
`replay-prices` or `prediction-drift-found` is announced. Each run reads
`config/securities.toml` and goes through each security listed there, one after the
other. For each security it asks the API for the same training as `make train`: the API
records the run, registers the model and promotes it if it is the security's first or
beats the production model. A run started by new or replayed prices, or by hand, trains
a security only when the API finds it needed: the security has no recorded training, the
feature drift check finds drift in its recent daily price changes, or its retraining
interval has been reached. A run started by `prediction-drift-found` trains every
configured security.

After the training, the run makes one scheduled forecast of each security through the
API, the same forecast as `make predict`, stored in the table `predictions` and marked
as scheduled. That task succeeds, and the pipeline announces the asset
`scheduled-forecasts`, also when the forecast of one security fails; the run then fails
at its last task. Forecasts that the web app, `make predict` or any other caller asks
for are not scheduled and take no part in the prediction drift check. While the replay
database exists, the run trains and forecasts on that database (see [Replay](#replay)).
Only one training-pipeline run goes at a time; announcements that arrive during a run
start one further run after it has ended. A failed run is not repeated.

The prediction drift check pipeline (`prediction_drift_check`) starts whenever the asset
`scheduled-forecasts` is announced. For each security listed in
`config/securities.toml`, one after the other, the pipeline asks the API to run the
prediction drift check. The API first decides whether a check is due. It does not check
when the security has fewer scheduled forecasts than the days of the drift window.
Otherwise it checks when the security has no earlier check, or when at least as many
stored trading days as the check interval have come after its latest check. When neither
holds, the check is not due. Its answer says whether it checked and which of these
reasons applied. A security without a production model gets an error instead, so its
check ends in an error.

A check works on two sets of forecasts made by the security's production model. The
first set holds the latest scheduled forecast of each of the last drift-window days that
have one; the model forecasts these days again from the inputs stored with their
scheduled forecasts. The second set holds the model's forecasts for every stored trading
day with a final close and complete inputs, up to the security's latest training. The
check tests whether the two sets differ. Each check is recorded as its own run in the
MLflow experiment `drift-checks`. While the replay database exists, the check reads that
database and records its runs in `replay-drift-checks` (see [Replay](#replay)). The
drift window, the check interval and the drift p-value threshold are in the table under
[Monitoring settings](#monitoring-settings).

When any check finds drift, the run announces the asset `prediction-drift-found`, and
that announcement starts the training pipeline for every security. When no check finds
drift, the task that announces drift is skipped, and nothing is announced. Only one run
of this pipeline goes at a time; announcements that arrive during a run start one
further run after it has ended. A failed run is not repeated.

A failed run shows its reason in the log of the failed task on the page, for example an
error EODHD answered with. For the daily update and replay pipelines, the full error is
in `docker compose logs data`. The training pipeline goes through every security even
when the training or the forecast of one fails: its task logs show each failure as it
happens. After the last security the run fails, and the log of its final task ends with
one message that lists each security that failed, with the reason the API gave or the
error reported when no answer came. The prediction drift check pipeline also asks for
the check of every security even when the check of one ends in an error. After the last
security, it first announces any drift it found and then fails, with the same kind of
message that lists each failed security. The API's log (`docker compose logs api`) holds
the full error.

A pipeline starts paused: switch it on with its toggle on the page. Switch on only one
of the daily update and replay pipelines at a time, and while either is on, run none of
`make load`, `make update`, `make replay` or `make replay-reset` by hand. The training
pipeline and the prediction drift check pipeline may be on with either of them and with
each other. While the training pipeline is on, start no training by hand, neither
`make train` nor a request to the API's `/training`: at most one training may run at a
time.

### Dataset versions
A training dataset gets a version id: its rows are written to `datasets/<symbol>.csv`
and recorded with [DVC](https://dvc.org) (Data Version Control), and DVC's fingerprint
of the file's content is the version id. The same rows always get the same id, and any
change in them gives a new one. DVC keeps a copy of every version under its id in
`datasets/.dvc/cache/` and pushes it to the `datasets` bucket of the object store (see
[Object store](#object-store)); identical data is stored only once. Training reads from
the database, never from these copies.

DVC runs here without Git: the copies stay on your machine, are never committed
(`datasets/` is gitignored) and are never deleted automatically.

### Model tracking
[MLflow](https://mlflow.org) records the training runs and holds the model registry.
`make mlflow` starts the MLflow server (and `make api` and the project commands start it
too); its page is on `localhost` at the port `MLFLOW_PORT` from `.env`. It keeps its run
and model records in its own database `mlflow` on the project's database server, with
its own login (`MLFLOW_DB_PASSWORD` in `.env`), both created on the first start, and
stores the model files in the object store (see [Object store](#object-store)). The API
and the project commands reach the server inside Docker at `http://mlflow:5000`.

Each configured security has the registered model `forecast-<symbol>` (for example
`forecast-AAPL.US`). Every training run is recorded, and its model is a new version of
that registered model. The version with the alias `production` is the security's
production model, the one `make predict` uses. Each run carries the tag `promoted`:
`true` when its model became the production model, `false` when it did not. The tag is
not updated later: a run whose model has since been replaced still shows `true`. While
the replay database exists, training and `make predict` use `replay-forecast-<symbol>`
instead (see [Replay](#replay)).

Each run also records its code version, in MLflow's standard tags
`mlflow.source.git.commit` (the commit) and `mlflow.source.git.dirty` (`true` when
tracked files had uncommitted changes, `false` when not). `make` captures both when it
builds the project image (see [Setup](#setup)), which every `make` command that runs
the image does first, so a run's tags describe the files as they were when `make` last
built the image that ran the training. An image not built with `make` records the
commit as `unknown` and has no `mlflow.source.git.dirty` tag.

MLflow's page for a run shows the commit next to the run's source, its first seven
characters; opening it shows the whole commit. The optional column "Version" in the
experiment's run list (switch it on in the column picker) shows the first six
characters of the commit, not the model version above. MLflow's pages do not show
`mlflow.source.git.dirty`. To find the runs trained on code with uncommitted changes,
enter `tags."mlflow.source.git.dirty" = "true"` in the search box above the run list;
runs without the tag are not listed.

### Object store
[SeaweedFS](https://github.com/seaweedfs/seaweedfs) runs in Docker (`object-store`) as
an S3-compatible object store for files that do not belong in PostgreSQL: MLflow's model
files (bucket `mlflow`) and DVC's dataset copies (bucket `datasets`). Both buckets are
created on the first start; the data lives in a Docker volume (`object-store-data`) and
survives restarts. Only the services inside Docker reach it (`OBJECT_STORE_USER` and
`OBJECT_STORE_PASSWORD` in `.env`); no port is published on the host.

### Monitoring
The API reports numbers about its own use. [Prometheus](https://prometheus.io) collects
them and [Grafana](https://grafana.com) draws them. `make monitoring` starts both with
the API; Grafana's page is on `localhost` at the port `GRAFANA_PORT` from `.env`. Log in
as `admin` with the password `GRAFANA_ADMIN_PASSWORD` from `.env`.

The API lists its numbers at `/metrics`: per route, how many requests came, how long
they took and which status group (2xx, 4xx, 5xx) they got. The health check and
`/metrics` itself are not counted. It also lists `trading_days_behind` per security: the
number of trading days after the latest stored day that were final when the security's
latest load ran; 0 means no trading day is behind. A security without a stored day or
without a recorded load has no number. Every load records per security when it fetched
it, also when it stored nothing, in the table `loads`.

The list also has `daily_updates_missed`, one number for the whole system: how many
scheduled daily updates since the latest recorded load of any security got no load
within the load limit (`load_limit_minutes`), the longest a load may run; 0 means none
was missed. The schedule is in `config/daily_update.toml`. The number is left out while
the database cannot be read, before the first load is recorded, and while the replay
database exists, since the member then switches the daily update pipeline off and the
replay pipeline on. Each call of `/metrics` measures `trading_days_behind` and
`daily_updates_missed` anew.

Prometheus collects the list regularly (see
[Monitoring settings](#monitoring-settings)). No port is published for it on the host;
its data lives in a Docker volume (`prometheus-data`) and survives restarts.

Prometheus also computes the error rate, the share of requests answered with a server
error (5xx) over a recent window, and stores it as `api:error_ratio:rate5m`. The formula
is written once, in `prometheus/rules.yml`; the dashboard and the alert rule "API error
rate" both read the stored value.

The dashboard "API" in the folder "Financial forecasting" shows these panels:

- requests per second, per route;
- the response time that 95% of requests stay under, per route;
- the error rate; a 404 (unknown security, or no production model yet) is not an error;
- the trading days behind, per security: green while up to date, red once behind.

Grafana's data source and the dashboard come from the files in `grafana/`, and Grafana
keeps no volume of its own. The dashboard is read-only on the page: a change goes into
`grafana/dashboards/api.json`.

#### Alerts
The alert rule "API error rate" fires when the error rate stays above its threshold for
the whole wait. The alert rule "Data not fresh" fires, one alert per security, when the
security's trading days behind stay above its threshold for the whole wait. The alert
rule "Daily update missed" fires when the number of missed daily updates stays above its
threshold for the whole wait.

In Grafana, open Alerting → Alert rules and look at the folder "Financial forecasting":
the rules are listed there with their state; an alert that fires is listed as firing.

#### Monitoring settings
| Setting | File |
|---|---|
| How often Prometheus collects the numbers | `prometheus/prometheus.yml` (`scrape_interval`) |
| How often Prometheus computes the error rate | `prometheus/prometheus.yml` (`evaluation_interval`) |
| Window of the error rate | `prometheus/rules.yml` (the range in the `rate(...)` expressions); the name `api:error_ratio:rate5m` carries the window and is read in `grafana/dashboards/api.json` and `grafana/provisioning/alerting/alerts.yaml` |
| How often Grafana checks the alert rules | `grafana/provisioning/alerting/alerts.yaml` (`interval`) |
| "API error rate": threshold | `grafana/provisioning/alerting/alerts.yaml` (`params`) |
| "API error rate": wait | `grafana/provisioning/alerting/alerts.yaml` (`for`) |
| "API error rate": without data | `grafana/provisioning/alerting/alerts.yaml` (`noDataState`) |
| "API error rate": when Prometheus cannot be asked | `grafana/provisioning/alerting/alerts.yaml` (`execErrState`) |
| "Data not fresh": threshold | `grafana/provisioning/alerting/alerts.yaml` (`params`) |
| "Data not fresh": wait | `grafana/provisioning/alerting/alerts.yaml` (`for`) |
| "Data not fresh": without data | `grafana/provisioning/alerting/alerts.yaml` (`noDataState`) |
| "Data not fresh": when Prometheus cannot be asked | `grafana/provisioning/alerting/alerts.yaml` (`execErrState`) |
| "Daily update missed": threshold | `grafana/provisioning/alerting/alerts.yaml` (`params`) |
| "Daily update missed": wait | `grafana/provisioning/alerting/alerts.yaml` (`for`) |
| "Daily update missed": without data | `grafana/provisioning/alerting/alerts.yaml` (`noDataState`) |
| "Daily update missed": when Prometheus cannot be asked | `grafana/provisioning/alerting/alerts.yaml` (`execErrState`) |
| Days the daily update runs on | `config/daily_update.toml` (`weekdays`) |
| Time zone of the daily update | `config/daily_update.toml` (`timezone`) |
| Time the final delay counts from: the daily update starts the final delay later | `config/daily_update.toml` (`start_after`) |
| Load limit: how long a load may run, and when a daily update counts as missed | `config/daily_update.toml` (`load_limit_minutes`) |
| Final delay after an exchange's close, for every load | `config/daily_update.toml` (`final_delay_minutes`) |
| "Trading days behind" panel: red from | `grafana/dashboards/api.json` (`thresholds`) |
| Drift p-value threshold: a drift check finds drift when its p-value is at or below it | `config/drift_checks.toml` (`drift_p_value_threshold`) |
| Drift window: how many of the latest days a drift check compares with the days up to the latest training (stored trading days for the feature drift check, days with a scheduled forecast for the prediction drift check) | `config/drift_checks.toml` (`drift_window_days`) |
| Check interval of the prediction drift check: how many stored trading days must pass after a security's latest check before the next one is due | `config/drift_checks.toml` (`prediction_drift_check_interval_days`) |

#### Known limitations
- Without data, every alert rule counts as OK: "API error rate" while no request came,
  "Data not fresh" while the database cannot be read and for a security without a stored
  day or a recorded load, and "Daily update missed" while the database cannot be read,
  before the first recorded load and while the replay database exists. A database that
  cannot be read shows as server errors on the API.
- A first server error after an API start is neither counted in the error rate nor shown
  in Grafana. The API creates the counter of a kind of request (route and status group)
  only when the first such request arrives, so Prometheus first collects it at 1, never
  at 0; rates come from the growth between two collections, and the step from 0 to 1 is
  never seen.
- No notification is sent anywhere; firing alerts are only listed in Grafana.

### Settings
Settings live in these files. `.env` holds the values for the member's own machine; the
other files hold the team's settings and are committed with the code. To change a
setting, edit its file:

- `.env`, a copy of `.env.example` that is never committed: the values for the member's
  own machine, each explained in `.env.example`. Among them are the database login and
  port, which stay as in `.env.example` because the tests log in with them (see
  [Setup](#setup)); the MLflow address for programs run on this machine outside Docker
  (`MLFLOW_TRACKING_URI`); the ports of the Airflow, MLflow, web app and Grafana pages
  and the logins of the Airflow and Grafana pages, plus the database logins of Airflow
  and MLflow; the object store's login; the first day of history (`HISTORY_START`); the
  replay's start and interval (`REPLAY_START`, `REPLAY_INTERVAL_SECONDS`); and the EODHD
  key (`EODHD_API_KEY`).
- `config/daily_update.toml`: when the daily update runs, how long a load may run and
  when a fetched price counts as final; its keys are in
  [Monitoring settings](#monitoring-settings).
- `config/securities.toml`: the securities the system loads, trains a model for and
  forecasts, each with its `symbol` and `exchange`. The file also lists market indices,
  which the system loads and checks for freshness but never trains a model for or
  forecasts: reference series that show the trend of the securities' markets.
- `config/training.toml`: how many of the latest trading days training holds back to
  score each model (`evaluation_days`), and after how many stored trading days a
  security is trained again (`retraining_interval_days`).
- `config/drift_checks.toml`: how many of the latest days a drift check compares (the
  drift window), after how many stored trading days the next prediction drift check of a
  security is due (the check interval), and the p-value at or below which a check finds
  drift; its keys are in [Monitoring settings](#monitoring-settings).
- `grafana/provisioning/alerting/alerts.yaml` and `grafana/dashboards/api.json`: the
  alert rules and the dashboard, both read-only on the Grafana page; their keys are in
  [Monitoring settings](#monitoring-settings).
- `prometheus/prometheus.yml` and `prometheus/rules.yml`: what Prometheus collects, how
  often, and the error rate it computes; their keys are in
  [Monitoring settings](#monitoring-settings).

Prometheus and Grafana read their files when they start: after a change, run
`docker compose restart prometheus` or `docker compose restart grafana`. Grafana also
picks up a changed dashboard file by itself within seconds. A change to the files in
`config/` takes effect:

- in the daily update pipeline, when Airflow next reads `airflow/dags/daily_update.py`,
  which it does regularly;
- in the data service, at its next load;
- in a command, when it next runs;
- in the API, after `docker compose restart api`.

A change to `config/securities.toml` reaches the training pipeline and the prediction
drift check pipeline at their next run, since each run reads the file. They call the
API, which knows only the securities listed when it started: until
`docker compose restart api`, each run trains, forecasts or checks the other securities
and then fails, naming the new security as unknown to the API.

A value in `config/daily_update.toml`, `config/training.toml` or
`config/drift_checks.toml` that is not allowed, such as a minute value outside its range
or one that is not a whole number, is refused: the commands, the API and the data
service then do not start, and after `docker compose restart api` the API stays down.
The allowed ranges are set in `src/forecasting/config.py`. When `make api`,
`make monitoring` or `make airflow` stops because a container exited,
`docker compose logs api` (or `docker compose logs data`) shows the reason.

### EODHD key
Prices, splits and dividends come from [EODHD](https://eodhd.com). Every member uses
their own key:

1. Register for the free tier at [eodhd.com](https://eodhd.com) and follow the
   instructions there to get your key.
2. Put it into `.env` as `EODHD_API_KEY=...`. `.env` is never committed.
3. Try it with `make contract`: it checks how EODHD delivers data with your key and
   skips, with its reason, a check your key cannot support.

## Documents
| Document | Content |
|---|---|
| [docs/requirements.md](docs/requirements.md) | Objectives, key metrics and requirements (generated from `docs/requirements.sdoc`) |
| [docs/plan.md](docs/plan.md) | Decisions, decision proposals, roadmap, phase plan, open points |
| [docs/team.md](docs/team.md) | Team setup: areas, meetings, communication, work tracking |
| [docs/dependencies.md](docs/dependencies.md) | Every Python package and what it does |
| [docs/decisions/](docs/decisions/) | One file per team decision: options and reasons |
| [references/](references/README.md) | Course brief, condensed: subject, schedule, checklist, reference architecture, evaluation |

## Editing the requirements
Edit `docs/requirements.sdoc`, then regenerate the readable version:

```bash
make requirements
```

StrictDoc is fetched by uv on first run.
