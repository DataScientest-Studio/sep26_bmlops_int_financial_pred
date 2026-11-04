# Financial forecasting service

Forecasts the next trading day's price change of a security and offers the forecast
through an API and an interactive app. An automated pipeline keeps it current: new
quotes are loaded, the model is retrained, a better model replaces the current one, and
the running system is monitored.

**Not investment advice.** Short-term prices move close to randomly; every model is
compared with simple baselines ("tomorrow's price equals today's", and the historical
mean change), and beating them is not expected.

Group project of the DataScientest MLOps bootcamp (sep26 cohort).

## Status
Under construction. Loading prices, splits and dividends from EODHD works (`make load`,
`make update`), and so does replaying stored history day by day (`make replay`), both
also on a schedule in Airflow (`make airflow`). The API reports numbers about its own
use, shown in Grafana (`make monitoring`). Training, forecasts and the app are not built
yet.

## Project structure
```
├── README.md
├── .github/workflows/
│   └── ci.yaml                  style check and unit tests on every push (GitHub Actions)
├── Makefile                     setup and maintenance commands
├── pyproject.toml               project metadata and packages
├── uv.lock                      exact versions of all packages, written by uv
├── .python-version              Python version
├── Dockerfile                   project image: the code with its locked packages, for the commands, the API, the data service and the MLflow server
├── .dockerignore                what the project image is built from
├── compose.yaml                 services run in Docker: the PostgreSQL database, the object store, the MLflow server, the API, the data service, Airflow, Prometheus, Grafana, and the project commands on demand
├── .env.example                 template for the local .env (database login, Airflow, MLflow and Grafana pages and logins, object-store login, model folder, first day of history, replay start and interval, EODHD key)
├── airflow/
│   └── dags/
│       ├── daily_update.py      the daily update pipeline: one load on the days and at the time config/daily_update.toml sets
│       ├── data_service_call.py  the call of the data service both pipelines make; a failed call fails the task with the reason the service answered
│       └── replay.py            the replay pipeline: one replayed trading day per interval
├── config/
│   ├── daily_update.toml        when the daily update loads, how long a load may run and when a fetched price is final
│   └── securities.toml          securities to forecast, with their exchange
├── db/
│   ├── init/
│   │   ├── dividends.sql        creates the dividends table where it is missing
│   │   ├── loads.sql            creates the loads table: each security's latest fetch time
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
├── models/                      trained models, written by the commands and the API in Docker (gitignored)
├── src/forecasting/             the service (skeleton: functions not built yet raise NotImplementedError)
│   ├── commands.py              commands the Makefile runs (load, replay, replay-reset, train, predict); the data service runs the same load and replay
│   ├── data_service.py          the data service: runs the load and the replay for the scheduled pipelines
│   ├── config.py                settings from .env and config/
│   ├── db.py                    database connection, reading prices, creating and dropping databases
│   ├── datasets.py              version ids of the training datasets, recorded with DVC
│   ├── trading_calendar.py      trading days of each exchange
│   ├── load.py                  loading prices, splits and dividends from a data source
│   ├── eodhd.py                 the EODHD data source
│   ├── replay.py                replay of stored history into a database of its own
│   ├── features.py              model inputs and target
│   ├── train.py                 training of one security's model
│   ├── evaluate.py              scores of model and baselines
│   ├── predict.py               next-trading-day forecast
│   ├── monitoring.py            drift checks
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
    └── run-as-owner.sh          starts the project image's commands, API and data service as the owner of models/
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

`.env` needs every setting of `.env.example`; a missing one is named in the error of the
first command or API request that reads the settings.

`make setup` installs the Python version from `.python-version` if missing and creates
`.venv/` with the packages pinned in `uv.lock`; tests and checks run from it.

`make db` starts the database on `localhost`, at the port set in `.env`. Its data lives
in a Docker volume and survives restarts. The tables `prices`, `splits`, `dividends` and
`loads` are created on the first start. The Compose service `db-tables` runs the scripts
in `db/init/` again at each start of the services; they only create the tables a
database lacks, so an existing database gains a table added to `db/init/` without a
reload. A change to a table that exists takes effect only on an empty volume
(`docker compose down --volumes` deletes the data).

`make load`, `make update`, `make replay`, `make replay-reset`, `make train`,
`make predict` and `make api` run in the project image (`Dockerfile`), with the packages
pinned in `uv.lock` and the settings of `.env`. Each rebuilds the image when the code
changed and starts the database, the object store and the MLflow server first if they
are not running. Trained models are kept in `models/` of the project folder and never
committed; the containers run as the owner of that folder, so the files belong to you.
Copies of the training datasets are kept the same way in `datasets/`.
`docker compose logs api` shows the API's output, errors included.

| Command | Effect |
|---|---|
| `make db` | start the database |
| `make db-stop` | stop it; the data is kept |
| `make db-shell` | SQL prompt in the database |
| `make load`, `make update` | load prices, splits and dividends from EODHD with your key: a security without stored prices from `HISTORY_START` on, otherwise only its new days; prints how many quotes were stored, replaced, rejected and missing |
| `make replay` | copy the next stored day from the database into the replay database; prints the day replayed (see "Replay" below) |
| `make replay-reset` | delete the replay database; the next `make replay` starts over from `REPLAY_START` |
| `make train` | train and save a model for each configured security on its final closes, holding back the latest `EVALUATION_DAYS` for scoring; prints its scores next to both baselines |
| `make predict` | print the newest model's forecast of the next trading day for each configured security |
| `make lint` | code style, formatting and type check (ruff, pyright); changes no files |
| `make test` | unit tests; needs no database |
| `make acceptance` | start the database, then run the black-box tests of the requirements and the integration tests against the database; the passed count shows progress |
| `make contract` | checks how EODHD delivers data, with your own key from `.env`; a check your key's history, remaining calls or plan cannot support is skipped with its reason |
| `make api` | start the API on http://localhost:8000, documentation at `/docs`; returns once it answers |
| `make api-stop` | stop the API |
| `make mlflow` | start the MLflow server with the database and the object store; its page is on `localhost` at the port `MLFLOW_PORT` from `.env` (see "Model tracking" below); returns once it answers |
| `make mlflow-stop` | stop the MLflow server and the object store; the database keeps running |
| `make airflow` | start Airflow with the data service; its page is on `localhost` at the port `AIRFLOW_PORT` from `.env` (see "Scheduled pipelines" below); returns once it answers |
| `make airflow-stop` | stop Airflow and the data service; the database keeps running |
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
latest stored day is copied, nothing is left to replay. `make replay-reset` deletes the
replay database to start over.

### Scheduled pipelines
Airflow runs the pipelines on a schedule. `make airflow` starts it; its page is on
`localhost` at the port `AIRFLOW_PORT` from `.env`. Log in as `admin` with the password
`AIRFLOW_ADMIN_PASSWORD` from `.env`. Airflow keeps its own database and login on the
project's database server, both created on the first start. Of the project's settings it
receives only `REPLAY_INTERVAL_SECONDS` from `.env` and the folder `config/`, which it
can read but not change; it never receives the EODHD key. Its tasks call the data
service, which runs the load and the replay inside Docker and is not reachable from the
host.

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
stored day is replayed, each run is skipped: switch the pipeline off.

Each pipeline announces its work, so that a pipeline waiting for new prices can start on
it: the daily update pipeline after each load as the asset `prices`, also after one that
found no new trading day, and the replay pipeline after each replayed day as the asset
`replay-prices`. The page lists both under "Assets". A skipped or failed run announces
nothing.

A failed run shows its reason in the log of the failed task on the page, for example an
error EODHD answered with; the full error is in `docker compose logs data`.

A pipeline starts paused: switch it on with its toggle on the page. Switch on only one
of the two pipelines at a time, and while either is on, run none of `make load`,
`make update`, `make replay` or `make replay-reset` by hand. Start at most one training
at a time.

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
replay pipeline on. Each call of `/metrics` measures
`trading_days_behind` and `daily_updates_missed` anew.

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
- the error rate; a 404 for an unknown security is not an error;
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

The alert rules are team configuration and read-only on the Grafana page. A change goes
into the file. Prometheus and Grafana read their files at start:
`docker compose restart prometheus` or `docker compose restart grafana`. A change to the
files in `config/` reaches the daily update pipeline when Airflow next reads
`airflow/dags/daily_update.py`, which it does regularly; the data service at its next
load; each command when it next runs; the API after `docker compose restart api`.

A value in `config/daily_update.toml` that is not allowed, such as a minute value
outside its range or not a whole number, is refused, and the API and the data service
then do not start, so a refused value also stops `docker compose restart api`. When
`make api`, `make monitoring` or `make airflow` stops because a container exited,
`docker compose logs api` (or `docker compose logs data`) shows the reason. The ranges
are set in `src/forecasting/config.py`.

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

### EODHD key
Prices, splits and dividends come from [EODHD](https://eodhd.com). Every member uses
their own key:

1. Register for the free plan at [eodhd.com](https://eodhd.com) and follow the
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
