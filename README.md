# Financial forecasting service

Forecasts the next trading day's price change of a security and offers the forecast through an API and an interactive app. An automated pipeline keeps it current: new quotes are loaded, the model is retrained, a better model replaces the current one, and the running system is monitored.

**Not investment advice.** Short-term prices move close to randomly; every model is compared with simple baselines ("tomorrow's price equals today's", and the historical mean change), and beating them is not expected.

Group project of the DataScientest MLOps bootcamp (sep26 cohort).

## Status
Planning. The service is not built yet.

## Project structure
```
├── README.md
├── Makefile                     setup and maintenance commands
├── pyproject.toml               project metadata and packages
├── uv.lock                      exact versions of all packages, written by uv
├── .python-version              Python version
├── compose.yaml                 services run in Docker: the PostgreSQL database
├── .env.example                 template for the local .env (database login, host, port, model folder)
├── config/
│   └── securities.toml          securities to forecast, with their exchange
├── db/
│   └── init/
│       └── prices.sql           creates the prices table on the database's first start
├── docs/
│   ├── requirements.sdoc        requirements source (StrictDoc)
│   ├── requirements.md          readable version, generated
│   ├── plan.md                  decision proposals, roadmap, phase plan, open points
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
├── src/forecasting/             the service (skeleton: functions not built yet raise NotImplementedError)
│   ├── config.py                settings from .env and config/
│   ├── db.py                    database connection, reading prices
│   ├── trading_calendar.py      trading days of each exchange
│   ├── load.py                  loading prices from a data source
│   ├── features.py              model inputs and target
│   ├── train.py                 training of one security's model
│   ├── evaluate.py              scores of model and baselines
│   ├── predict.py               next-trading-day forecast
│   ├── monitoring.py            drift checks
│   └── api/                     FastAPI app, endpoints, request and response bodies
├── tests/
│   ├── acceptance/              black-box tests, one or more per testable requirement
│   ├── unit/                    tests of single functions and the API wiring
│   ├── conftest.py              shared fixtures: a test database per worker, API client
│   └── fakes.py                 stand-in data source with generated prices
└── tools/
    └── export-requirements.sh   regenerates docs/requirements.md
```

## Setup
Needs [uv](https://docs.astral.sh/uv/), `make` and Docker with Compose. From a fresh clone:

```bash
cp .env.example .env      # then set your own password in .env
make setup                # Python environment in .venv/
make db                   # starts PostgreSQL, waits until it is ready
```

`make setup` installs the Python version from `.python-version` if missing and creates `.venv/` with the packages pinned in `uv.lock`.

`make db` starts the database on `localhost`, at the port set in `.env`. Its data lives in a Docker volume and survives restarts. The `prices` table is created on the first start; a later change to `db/init/` takes effect only on an empty volume (`docker compose down --volumes` deletes the data).

| Command | Effect |
|---|---|
| `make db` | start the database |
| `make db-stop` | stop it; the data is kept |
| `make db-shell` | SQL prompt in the database |
| `make test` | unit and integration tests (needs `make db`) |
| `make acceptance` | black-box tests of the requirements; the passed count shows progress |
| `make api` | API on http://localhost:8000, documentation at `/docs` |

## Documents
| Document | Content |
|---|---|
| [docs/requirements.md](docs/requirements.md) | Objectives, key metrics and requirements (generated from `docs/requirements.sdoc`) |
| [docs/plan.md](docs/plan.md) | Decision proposals, roadmap, phase plan, open points |
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
