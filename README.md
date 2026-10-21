# Financial forecasting service

Forecasts the next trading day's price change of a security and offers the forecast through an API and an interactive app. An automated pipeline keeps it current: new quotes are loaded, the model is retrained, a better model replaces the current one, and the running system is monitored.

**Not investment advice.** Short-term prices move close to randomly; every model is compared with simple baselines ("tomorrow's price equals today's", and the historical mean change), and beating them is not expected.

Group project of the DataScientest MLOps bootcamp (sep26 cohort).

## Status
Under construction. Loading prices, splits and dividends from EODHD works (`make load`, `make update`), and so does replaying stored history day by day (`make replay`); training, forecasts and the app are not built yet.

## Project structure
```
├── README.md
├── .github/workflows/
│   └── ci.yaml                  style check and unit tests on every push (GitHub Actions)
├── Makefile                     setup and maintenance commands
├── pyproject.toml               project metadata and packages
├── uv.lock                      exact versions of all packages, written by uv
├── .python-version              Python version
├── Dockerfile                   project image: the code with its locked packages, for the commands and the API
├── .dockerignore                what the project image is built from
├── compose.yaml                 services run in Docker: the PostgreSQL database, the API, and the project commands on demand
├── .env.example                 template for the local .env (database login, model folder, first day of history, replay start, EODHD key)
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
├── models/                      trained models, written by the commands and the API in Docker (gitignored)
├── src/forecasting/             the service (skeleton: functions not built yet raise NotImplementedError)
│   ├── commands.py              commands the Makefile runs (load, replay, replay-reset)
│   ├── config.py                settings from .env and config/
│   ├── db.py                    database connection, reading prices, creating and dropping databases
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
│   ├── unit/                    tests of single functions and the API wiring
│   ├── conftest.py              shared fixtures: a test database per worker, API client
│   └── fakes.py                 stand-in data source with generated prices
└── tools/
    ├── export-requirements.sh   regenerates docs/requirements.md
    └── run-as-owner.sh          starts the project image's commands and API as the owner of models/
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

`make load`, `make update`, `make replay`, `make replay-reset` and `make api` run in the project image (`Dockerfile`), with the packages pinned in `uv.lock` and the settings of `.env`. Each rebuilds the image when the code changed and starts the database first if it is not running. Trained models are kept in `models/` of the project folder and never committed; the containers run as the owner of that folder, so the files belong to you. `docker compose logs api` shows the API's output, errors included.

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
