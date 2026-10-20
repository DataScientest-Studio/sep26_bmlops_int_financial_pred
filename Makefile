.PHONY: setup requirements lint \
        db db-stop db-shell \
        load update replay replay-reset \
        test acceptance contract \
        api

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

# Loads prices, splits and dividends from EODHD with the key in .env: a security without
# stored prices from HISTORY_START on, otherwise only the days from its latest stored
# one on. Both names run the same load.
update load:
	uv run --env-file .env python -m forecasting.commands load

# Copies the next stored day from the database into the replay database; the first run
# fills it up to REPLAY_START. Prints the day replayed.
replay:
	uv run --env-file .env python -m forecasting.commands replay

# Deletes the replay database; the next replay starts over from REPLAY_START.
replay-reset:
	uv run --env-file .env python -m forecasting.commands replay-reset

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

# Starts the API on http://localhost:8000 (docs at /docs).
api:
	uv run --env-file .env uvicorn forecasting.api.app:app --reload
