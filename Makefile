.PHONY: setup requirements lint db db-stop db-shell test acceptance api

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

# Tests see only the settings of .env.example: the shell's own variables are cleared,
# apart from PATH and HOME, which uv needs.
TEST_ENV = env -i PATH="$$PATH" HOME="$$HOME" uv run --env-file .env.example

# Runs unit and integration tests in parallel; needs the database (make db) with the
# login from .env.example.
test:
	$(TEST_ENV) pytest -n auto -m "not acceptance"

# Runs the black-box tests of the requirements; the passed count shows progress.
acceptance:
	$(TEST_ENV) pytest -n auto -m acceptance

# Starts the API on http://localhost:8000 (docs at /docs).
api:
	uv run --env-file .env uvicorn forecasting.api.app:app --reload
