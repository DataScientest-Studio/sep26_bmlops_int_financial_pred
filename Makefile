.PHONY: setup requirements lint \
        db db-stop db-shell \
        load update replay replay-reset reset train predict \
        test acceptance contract \
        api api-stop \
        webapp webapp-stop \
        mlflow mlflow-stop \
        airflow airflow-stop \
        monitoring monitoring-stop

# Python finds the project's packages in .venv only; a PYTHONPATH set in the shell
# (for example by ROS) would put foreign packages and pytest plugins first.
unexport PYTHONPATH

# Commit the project image is built from, and whether tracked files had uncommitted
# changes (true or false).
export CODE_COMMIT = $(shell git rev-parse HEAD)
export CODE_HAS_UNCOMMITTED_CHANGES = $(if $(shell git status --porcelain --untracked-files=no),true,false)

# This Makefile builds every image without the provenance record that BuildKit adds by
# default. That record changes with every build, so an unchanged image would get a new
# id. Compose would then restart the services that run the image, such as the MLflow
# server, even while the API is using it. The record is for published images, and the
# project publishes none.
export BUILDX_NO_DEFAULT_ATTESTATIONS = 1

# Creates .venv with the pinned Python and the locked packages.
setup:
	uv sync --locked

# Regenerates docs/requirements.md from docs/requirements.sdoc.
requirements:
	tools/export-requirements.sh

# Checks code style, formatting and types; changes no files.
lint:
	uv run ruff check
	uv run ruff format --check
	uv run pyright

# Starts the database and waits until it accepts connections.
db:
	docker compose up --detach --wait db

# Stops the database; the data volume is kept.
db-stop:
	docker compose stop db

# Opens an SQL prompt in the database.
db-shell:
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

# Runs a project command in the project image, rebuilt when the code changed; starts the
# database, the object store and the MLflow server first if they are not running. The
# datasets folder is created first if missing.
COMMAND_ENV = mkdir -p datasets && docker compose run --rm --build commands

# Loads prices, splits and dividends from EODHD with the key in .env: a security without
# stored prices from HISTORY_START on, otherwise only the days from its latest stored
# one on. Both names run the same load.
update load:
	$(COMMAND_ENV) load

# Copies the next stored day from the database into the replay database; the first run
# fills it up to REPLAY_START. Prints the day replayed.
replay:
	$(COMMAND_ENV) replay

# Deletes the replay database and the replay runs and models in MLflow, model files
# included, and removes for good everything deleted on the MLflow page. Training and
# forecasts return to the member's own database and models; the next replay starts over
# from REPLAY_START.
replay-reset:
	$(COMMAND_ENV) replay-reset
	docker compose exec -e MLFLOW_TRACKING_URI=http://localhost:5000 mlflow \
		sh -c 'mlflow gc --backend-store-uri "$$MLFLOW_BACKEND_STORE_URI"'

# Stops every service and deletes everything stored: the database with prices, forecasts
# and the records of MLflow and Airflow, the object store, the pipeline logs, the
# monitoring history and the dataset copies. The next start creates every table from
# db/init; make update loads the history again.
reset:
	docker compose --profile commands down --volumes
	find datasets -mindepth 1 ! -name .gitkeep -delete

# Trains a model for each configured security on its final closes, holding back the
# latest evaluation_days of config/training.toml for scoring; before training a security
# with a recorded training, records a feature drift check in MLflow; records the run and
# registers the model in MLflow, promotes it if it is the first or beats the production
# model, and prints its scores next to both baselines. A security that fails does not
# stop the others: at the end the command fails and names each failed security with its
# reason.
train:
	$(COMMAND_ENV) train

# Prints the production model's forecast of the next trading day for each configured
# security. A security that fails does not stop the others: at the end the command fails
# and names each failed security with its reason.
predict:
	$(COMMAND_ENV) predict

# Tests see only the settings of .env.example: the shell's own variables are cleared,
# apart from PATH and HOME, which uv needs. MLflow sends no usage reports to its makers.
TEST_ENV = env -i PATH="$$PATH" HOME="$$HOME" MLFLOW_DISABLE_TELEMETRY=true uv run --env-file .env.example

# Runs the unit tests in parallel; needs no database.
test:
	$(TEST_ENV) pytest -n auto -m "not acceptance and not integration and not eodhd"

# Starts the database, then runs the black-box tests of the requirements and the
# integration tests against the database; the passed count shows progress.
acceptance: db
	$(TEST_ENV) pytest -n auto -m "acceptance or integration"

# Checks how EODHD delivers data, with your own key from .env; a check your key's
# history, remaining calls or plan cannot support is skipped with its reason. Short
# tracebacks never show the key. MLflow sends no usage reports to its makers.
contract:
	MLFLOW_DISABLE_TELEMETRY=true uv run --env-file .env pytest -n auto --dist loadscope -m eodhd --tb=short

# Starts the API in the project image, rebuilt when the code changed, on
# http://localhost:8000 (docs at /docs); returns once it answers.
api:
	mkdir -p datasets
	docker compose up --build --detach --wait api

# Stops the API.
api-stop:
	docker compose stop api

# Starts the web app and the API it calls, rebuilt when the code changed; returns once
# the app answers on localhost at the port WEBAPP_PORT from .env.
webapp:
	mkdir -p datasets
	docker compose up --build --detach --wait webapp

# Stops the web app; the API keeps running.
webapp-stop:
	docker compose stop webapp

# Starts the MLflow server, its page, the database and the object store, rebuilding the
# server if pyproject.toml, uv.lock or .python-version changed; returns once it answers
# on localhost at the port MLFLOW_PORT from .env.
mlflow:
	docker compose up --build --detach --wait mlflow

# Stops the MLflow server and the object store; the database keeps running.
mlflow-stop:
	docker compose stop mlflow object-store

# Airflow's services that keep running; its database and init steps run once on the way.
AIRFLOW_SERVICES = airflow-apiserver airflow-scheduler airflow-dag-processor

# Starts Airflow with the database, the data service and the API, rebuilt when the code
# changed; returns once its page answers on localhost at the port AIRFLOW_PORT from
# .env.
airflow:
	mkdir -p datasets
	docker compose up --build --detach --wait $(AIRFLOW_SERVICES)

# Stops Airflow and the data service; the database and the API keep running.
airflow-stop:
	docker compose stop $(AIRFLOW_SERVICES) data

# The monitoring services.
MONITORING_SERVICES = prometheus grafana

# Starts Prometheus and Grafana with the API, rebuilt when the code changed; returns
# once the Grafana page answers on localhost at the port GRAFANA_PORT from .env.
monitoring:
	mkdir -p datasets
	docker compose up --build --detach --wait api $(MONITORING_SERVICES)

# Stops Prometheus and Grafana; the API keeps running.
monitoring-stop:
	docker compose stop $(MONITORING_SERVICES)
