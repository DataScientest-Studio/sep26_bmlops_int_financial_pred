# Image of the web app: the webapp group's packages, without the service's code.
FROM python:3.12.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

# uv uses the image's Python and keeps no download cache in the image.
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /app

# Installs only the webapp group's packages before the app, so an app change reuses
# this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --only-group webapp
ENV PATH="/app/.venv/bin:$PATH"

COPY webapp/ webapp/
WORKDIR /app/webapp
# The app writes nothing, so it runs as the unprivileged account nobody.
USER nobody
CMD ["streamlit", "run", "app.py"]
