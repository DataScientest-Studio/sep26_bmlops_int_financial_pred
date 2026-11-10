# Images of the project, in two stages. The stage `packages` holds the locked runtime
# packages and is the image of the MLflow server. The last stage, `project`, adds the
# code and is the image of the commands, the API and the data service.
# @relation(REQ-AUT-006, scope=file)

FROM python:3.12.14-slim-bookworm AS packages
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

# uv uses the image's Python, keeps no download cache in the image and compiles the
# installed packages at build, so containers start without compiling them.
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_COMPILE_BYTECODE=1
WORKDIR /app

# Installs the packages before the code, so a code change reuses this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-default-groups --no-install-project
ENV PATH="/app/.venv/bin:$PATH"

FROM packages AS project

# The package build reads README.md as the project's description (pyproject.toml).
COPY README.md ./
COPY src/ src/
COPY db/init/ db/init/
RUN uv sync --locked --no-default-groups

# Passed in by `make` when it builds the image: the commit and whether tracked files had
# uncommitted changes ("true" or "false"). An image not built by `make` records the
# commit as "unknown" and leaves unknown whether tracked files had uncommitted changes.
ARG CODE_COMMIT=unknown
ENV CODE_COMMIT=${CODE_COMMIT}
ARG CODE_HAS_UNCOMMITTED_CHANGES=
ENV CODE_HAS_UNCOMMITTED_CHANGES=${CODE_HAS_UNCOMMITTED_CHANGES}

# The image carries neither Git nor the repository's .git folder;
# GIT_PYTHON_REFRESH=quiet keeps MLflow's Git lookup from warning when it finds
# neither. The code version comes from CODE_COMMIT and CODE_HAS_UNCOMMITTED_CHANGES.
ENV GIT_PYTHON_REFRESH=quiet

COPY tools/run-as-owner.sh /usr/local/bin/run-as-owner
ENTRYPOINT ["run-as-owner"]
