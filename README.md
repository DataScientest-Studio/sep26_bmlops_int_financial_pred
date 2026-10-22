# Financial forecasting service

Forecasts the next trading day's price change of a security and offers the forecast through an API and an interactive app. An automated pipeline keeps it current: new quotes are loaded, the model is retrained, a better model replaces the current one, and the running system is monitored.

**Not investment advice.** Short-term prices move close to randomly; every model is compared with simple baselines ("tomorrow's price equals today's", and the historical mean change), and beating them is not expected.

Group project of the DataScientest MLOps bootcamp (sep26 cohort).

## Status
Under construction. Loading prices, splits and dividends from EODHD works (`make load`, `make update`), and so does replaying stored history day by day (`make replay`), both also on a schedule in Airflow (`make airflow`); training, forecasts and the app are not built yet.

## Project structure
```
├── README.md
├── .github/workflows/
│   └── ci.yaml                  style check and unit tests on every push (GitHub Actions)
├── Makefile                     setup and maintenance commands
├── pyproject.toml               project metadata and packages
├── uv.lock                      exact versions of all packages, written by uv
├── .python-version              Python version
├── Dockerfile                   project image: the code with its locked packages, for the commands, the API and the data service
├── .dockerignore                what the project image is built from
├── compose.yaml                 services run in Docker: the PostgreSQL database, the API, the data service, Airflow, and the project commands on demand
├── .env.example                 template for the local .env (database login, Airflow page and logins, model folder, first day of history, replay start and interval, EODHD key)
├── airflow/
│   ├── create-database.sql      creates Airflow's own database and login on the project's database server
│   └── dags/
│       ├── daily_update.py      the daily update pipeline: one load on every weekday after the US close
│       └── replay.py            the replay pipeline: one replayed trading day per interval
├── config/
│   └── securities.toml          securities to forecast, with their exchange
├── db/
│   ├── init/
│   │   ├── dividends.sql        creates the dividends table on the database's first start
│   │   ├── prices.sql           creates the prices table on the database's first start
│   │   └── splits.sql           creates the splits table on the database's first start
│   └── queries/
│       ├── examples.sql         example queries on the prices table
│       ├── sample-data.sql      made-up prices for trying them
│       └── remove-sample-data.sql  removes the made-up prices again
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
│   ├── commands.py              commands the Makefile runs (load, replay, replay-reset); the data service runs the same load and replay
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
│   └── api/                     FastAPI app, endpoints, request and response bodies
├── tests/
│   ├── acceptance/              black-box tests, one or more per testable requirement
│   ├── contract/                checks of how EODHD delivers data, run with your own key
│   ├── unit/                    tests of single functions and the wiring of the API and the data service
│   ├── conftest.py              shared fixtures: a test database per worker, API client
│   └── fakes.py                 stand-in data source with generated prices
└── tools/
    ├── export-requirements.sh   regenerates docs/requirements.md
    └── run-as-owner.sh          starts the project image's commands, API and data service as the owner of models/
```

## Setup
Needs [uv](https://docs.astral.sh/uv/), `make` and Docker with Compose. From a fresh clone:

```bash
cp .env.example .env      # then add your own EODHD key (see "EODHD key" below); keep the development login
make setup                # Python environment in .venv/
make db                   # starts PostgreSQL, waits until it is ready
make load                 # builds the project image, loads the price history from EODHD
```

After that, `make update` once a day adds the new trading days.

`.env` needs every setting of `.env.example`; a missing one is named in the error of the first command or API request that reads the settings.

`make setup` installs the Python version from `.python-version` if missing and creates `.venv/` with the packages pinned in `uv.lock`; tests and checks run from it.

`make db` starts the database on `localhost`, at the port set in `.env`. Its data lives in a Docker volume and survives restarts. The tables `prices`, `splits` and `dividends` are created on the first start; a later change to `db/init/` takes effect only on an empty volume (`docker compose down --volumes` deletes the data).

`make load`, `make update`, `make replay`, `make replay-reset` and `make api` run in the project image (`Dockerfile`), with the packages pinned in `uv.lock` and the settings of `.env`. Each rebuilds the image when the code changed and starts the database first if it is not running. Trained models are kept in `models/` of the project folder and never committed; the containers run as the owner of that folder, so the files belong to you. Copies of the training datasets are kept the same way in `datasets/`. `docker compose logs api` shows the API's output, errors included.

| Command | Effect |
|---|---|
| `make db` | start the database |
| `make db-stop` | stop it; the data is kept |
| `make db-shell` | SQL prompt in the database |
| `make load`, `make update` | load prices, splits and dividends from EODHD with your key: a security without stored prices from `HISTORY_START` on, otherwise only its new days; prints how many quotes were stored, replaced, rejected and missing |
| `make replay` | copy the next stored day from the database into the replay database; prints the day replayed (see "Replay" below) |
| `make replay-reset` | delete the replay database; the next `make replay` starts over from `REPLAY_START` |
| `make lint` | code style, formatting and type check (ruff, pyright); changes no files |
| `make test` | unit tests; needs no database |
| `make acceptance` | black-box tests of the requirements; the passed count shows progress |
| `make contract` | checks how EODHD delivers data, with your own key from `.env`; a check your key's history, remaining calls or plan cannot support is skipped with its reason |
| `make api` | start the API on http://localhost:8000, documentation at `/docs`; returns once it answers |
| `make api-stop` | stop the API |
| `make airflow` | start Airflow with the data service; its page is on http://localhost:8080 (see "Scheduled pipelines" below); returns once it answers |
| `make airflow-stop` | stop Airflow and the data service; the database keeps running |

`make db-shell` opens an SQL prompt (`\q` leaves it). For example, the latest day stored per security:

```sql
SELECT symbol, max(day) AS latest_day, count(*) AS days
FROM prices
GROUP BY symbol;
```

More examples are in `db/queries/examples.sql`. Run a file with:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/queries/examples.sql
```

To try the examples before real prices are loaded, run `db/queries/sample-data.sql` the same way. It adds made-up prices under the symbols `AAPL.SAMPLE` and `SAP.SAMPLE`; the suffix keeps them apart from real prices, which are stored as `AAPL.US` and `SAP.XETRA`. `db/queries/remove-sample-data.sql` removes them again:

```sql
DELETE FROM prices WHERE symbol LIKE '%.SAMPLE';
```

`LIKE '%.SAMPLE'` matches every symbol that ends in `.SAMPLE` (`%` stands for any text), so real prices are never deleted.

### Replay
Replay plays stored history back one trading day at a time, as if each day were arriving live, so the pipeline can be shown over weeks of data within minutes. It copies prices, splits and dividends from the database into a database of its own on the same server, named after it with `_replay` (`forecasting_replay` for `forecasting`), and only reads the database it copies from; it makes no EODHD calls. The first `make replay` creates the replay database and fills it with every stored day up to `REPLAY_START`, which must lie between the first and the latest stored day. Each later run copies the replay database's latest day again, so a price that has become final since replaces the provisional one, and then the next stored day. Each run copies all or nothing. Once the latest stored day is copied, nothing is left to replay. `make replay-reset` deletes the replay database to start over.

### Scheduled pipelines
Airflow runs the pipelines on a schedule. `make airflow` starts it; its page is on http://localhost:8080 (the port is `AIRFLOW_PORT` in `.env`). Log in as `admin` with the password `AIRFLOW_ADMIN_PASSWORD` from `.env`. Airflow keeps its own database and login on the project's database server, both created on the first start, and it receives none of the project's settings apart from `FINAL_DELAY_MINUTES` and `REPLAY_INTERVAL_SECONDS`, never the EODHD key. Its tasks call the data service, which runs the load and the replay inside Docker and is not reachable from the host.

The daily update pipeline (`daily_update`) runs one load on every weekday at 16:00 New York time plus `FINAL_DELAY_MINUTES`, the same load as `make update`. A failed run is not repeated, since a load uses the free tier's calls of the day; a run missed while Airflow was stopped is made up once if Airflow starts again on the same New York day, and skipped from the next day on; either way the next load fetches from the latest stored day on.

The replay pipeline (`replay`) replays one trading day every `REPLAY_INTERVAL_SECONDS` seconds, the same replay as `make replay` (see [Replay](#replay)). Airflow refuses to load it while the interval lies outside its limits and names them on its page. A missed run is not made up, and a run that is still going delays the next one. Once the latest stored day is replayed, each run is skipped: switch the pipeline off.

Each pipeline announces its work, so that a pipeline waiting for new prices can start on it: the daily update after each load as the asset `prices`, also after one that found no new trading day, and the replay pipeline after each replayed day as the asset `replay-prices`. The page lists both under "Assets". A skipped or failed run announces nothing.

A pipeline starts paused: switch it on with its toggle on the page. Switch on only one of the two pipelines at a time, and while either is on, run none of `make load`, `make update`, `make replay` or `make replay-reset` by hand. Start at most one training at a time.

### Dataset versions
A training dataset gets a version id: its rows are written to `datasets/<symbol>.csv` and recorded with [DVC](https://dvc.org) (Data Version Control), and DVC's fingerprint of the file's content is the version id. The same rows always get the same id, and any change in them gives a new one. DVC keeps a copy of every version in `datasets/.dvc/cache/`, named after its id; identical data is stored only once. Training reads from the database, never from these copies.

DVC runs here without Git and without a remote: the copies stay on your machine, are never committed (`datasets/` is gitignored) and are never deleted automatically. Deleting `datasets/` loses these copies.

### EODHD key
Prices, splits and dividends come from [EODHD](https://eodhd.com). Every member uses their own key:

1. Register for the free plan at [eodhd.com](https://eodhd.com) and follow the instructions there to get your key.
2. Put it into `.env` as `EODHD_API_KEY=...`. `.env` is never committed.
3. Try it with `make contract`: it checks how EODHD delivers data with your key and skips, with its reason, a check your key cannot support.

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
