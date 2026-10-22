# Dependencies

Every package the project declares in `pyproject.toml`, what it does and where we use it. Exact versions are in `uv.lock`; `make setup` installs them. Packages these pull in themselves (numpy, pydantic, starlette …) are not listed.

## Runtime

| Package | What it does | Used for |
|---|---|---|
| fastapi | Web framework for HTTP APIs: turns Python functions into endpoints, checks request and response bodies, and generates the interactive documentation at `/docs`. | The API (`forecasting.api`): `/health`, `/training`, `/predict`; the data service (`forecasting.data_service`): `/health`, `/load`, `/replay`. |
| uvicorn | Web server that runs a FastAPI application and listens on a port. | The `api` service (`make api`) and the `data` service. |
| pandas | Tables in memory (DataFrame): reading query results, computing changes and rolling values over days. | Prices, features, target, evaluation. |
| scikit-learn | Machine-learning library: regression models, metrics, preprocessing. | The model (Ridge, see `decisions/regressors.md`) and its error metrics. |
| mlflow | Experiment tracking and model registry: records each training run's parameters, metrics, versions and model files, registers models and marks which version is in production. | The MLflow server (`make mlflow`) and recording training runs (`forecasting.train`). |
| boto3 | Client for S3-compatible object stores: uploads and downloads files over the S3 protocol. MLflow uses it underneath when its model files live in an `s3://` bucket. | The MLflow server and its clients storing and reading model files in the object store (SeaweedFS). |
| sqlalchemy | Database toolkit: one way to connect to and query SQL databases, independent of the database product; pandas reads and writes tables through it. | Connection to PostgreSQL (`forecasting.db`), reading and writing prices. |
| psycopg (with `binary`) | The PostgreSQL driver for Python: the part that actually talks to the PostgreSQL server over the network. SQLAlchemy uses it underneath (`postgresql+psycopg://…` in the connection URL). `binary` installs a ready-built version, so no compiler or PostgreSQL client libraries are needed. | Every database connection; the test fixtures use it directly to create and drop test databases. |
| exchange-calendars | Trading calendars of about 100 exchanges: trading days, holidays, early closes, time zones. | `forecasting.trading_calendar` (see `decisions/trading-calendar.md`). |
| dvc | Data Version Control: records a file under a fingerprint of its content and keeps a copy of each version, so any version can be brought back. We run it without Git and without a remote: the copies stay on the member's own machine. | The version id of each training dataset (`forecasting.datasets`); the copies are kept in `datasets/`. |
| pyyaml | Reads and writes YAML, a text format for structured data. | Reading the version id from the record file DVC writes next to each dataset (`forecasting.datasets`). |
| httpx2 | HTTP client library, the successor of `httpx`: sends requests to web services and reads their answers. FastAPI's test client is built on it too: tests send requests to the API in memory, without starting a server or opening a port. | Fetching prices, splits and dividends from EODHD (`forecasting.eodhd`); API tests (`fastapi.testclient.TestClient`); `make contract`. |

## Development only (`dev` group)

| Package | What it does | Used for |
|---|---|---|
| pytest | Test framework: finds functions named `test_…`, runs them and reports failures. | All tests: `make test`, `make acceptance`, `make contract`. |
| pytest-xdist | Runs tests in several worker processes at once (`-n auto`: one per CPU core). | Faster test runs; each worker gets its own test database. |
| ruff | Linter and formatter: finds errors and style problems, formats code (88 characters per line, Google-style docstrings). | `make lint` (also on every push); `uv run ruff format` formats the code. |
| pyright | Type checker: finds calls with arguments or results of the wrong type before the code runs. VS Code's Pylance is built on it, so the editor and `make lint` report the same. The `nodejs` extra installs the Node.js runtime it needs. | `make lint` (also on every push). |
| pandas-stubs | Type information for pandas, published by the pandas project: tells the type checker what each pandas call accepts and returns. | Correct type checks of pandas code (pyright, Pylance). |

## In Airflow's image

The pipelines in `airflow/dags/` run in Airflow's own image, which holds none of the project's packages; they use only packages that image brings along.

| Package | What it does | Used for |
|---|---|---|
| requests | HTTP client library: sends requests to web services and reads their answers. | The pipelines' calls to the data service. |
| pendulum | Dates and times with time zones. | The pipelines' schedule and the New York day. |

## Tools run without installing

| Tool | What it does | Used for |
|---|---|---|
| strictdoc (via `uvx`, pinned in `tools/export-requirements.sh`) | Requirements tool: checks `requirements.sdoc` and exports it. | `make requirements`. |
