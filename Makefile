.PHONY: setup requirements lint \
        db db-stop db-shell \
        load update replay replay-reset \
        test acceptance contract \
        api api-stop \
        airflow airflow-stop

# Python finds the project's packages in .venv only; a PYTHONPATH set in the shell
# (for example by ROS) would put foreign packages and pytest plugins first.
unexport PYTHONPATH

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
# database first if it is not running. The models and datasets folders are created
# first if missing.
COMMAND_ENV = mkdir -p models datasets && docker compose run --rm --build commands

# Loads prices, splits and dividends from EODHD with the key in .env: a security without
# stored prices from HISTORY_START on, otherwise only the days from its latest stored
# one on. Both names run the same load.
update load:
	$(COMMAND_ENV) load

# Copies the next stored day from the database into the replay database; the first run
# fills it up to REPLAY_START. Prints the day replayed.
replay:
	$(COMMAND_ENV) replay

# Deletes the replay database; the next replay starts over from REPLAY_START.
replay-reset:
	$(COMMAND_ENV) replay-reset

# Tests see only the settings of .env.example: the shell's own variables are cleared,
# apart from PATH and HOME, which uv needs.
TEST_ENV = env -i PATH="$$PATH" HOME="$$HOME" uv run --env-file .env.example

# Runs the unit tests in parallel; needs no database.
test:
	$(TEST_ENV) pytest -n auto -m "not acceptance and not eodhd"

# Runs the black-box tests of the requirements; the passed count shows progress.
acceptance:
	$(TEST_ENV) pytest -n auto -m acceptance

# Checks how EODHD delivers data, with your own key from .env; a check your key's
# history, remaining calls or plan cannot support is skipped with its reason. Short
# tracebacks never show the key.
contract:
	uv run --env-file .env pytest -n auto -m eodhd --tb=short

# Starts the API in the project image, rebuilt when the code changed, on
# http://localhost:8000 (docs at /docs); returns once it answers.
api:
	mkdir -p models datasets
	docker compose up --build --detach --wait api

# Stops the API.
api-stop:
	docker compose stop api

# Airflow's services that keep running; its database and init steps run once on the way.
AIRFLOW_SERVICES = airflow-apiserver airflow-scheduler airflow-dag-processor

# Starts Airflow with the database and the data service, rebuilt when the code changed;
# returns once its page answers on http://localhost:8080 (AIRFLOW_PORT in .env).
airflow:
	mkdir -p models datasets
	docker compose up --build --detach --wait $(AIRFLOW_SERVICES)

# Stops Airflow and the data service; the database keeps running.
airflow-stop:
	docker compose stop $(AIRFLOW_SERVICES) data
