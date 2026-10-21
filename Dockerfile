# Project image of the commands and the API: the code with the locked runtime packages.
FROM python:3.12.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

# uv uses the image's Python and keeps no download cache in the image.
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /app

# Installs the packages before the code, so a code change reuses this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

# The package build reads README.md as the project's description (pyproject.toml).
COPY README.md ./
COPY src/ src/
COPY config/ config/
COPY db/init/ db/init/
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"

COPY tools/run-as-owner.sh /usr/local/bin/run-as-owner
ENTRYPOINT ["run-as-owner"]
