# Security

What the forecasting service holds, who can reach it, and how. It runs on one local
machine per member, as Docker Compose services. A member is whoever runs a copy of the
system. How the system is built is in [ARCHITECTURE.md], and how it is installed and run
is in [DEPLOYMENT.md].

[ARCHITECTURE.md]: ARCHITECTURE.md
[DEPLOYMENT.md]: DEPLOYMENT.md

## Data handled

-   **Market data.** The service stores prices, splits and dividends from EODHD in the
    member's own database, in the dataset copies under `datasets/` and in the object
    store's bucket `datasets`. EODHD's licence terms allow personal use and no
    redistribution. Each member therefore uses their own free key and a private
    database. No data passes between members, and no price data is ever committed
    (`.gitignore` leaves out `datasets/`, CSV files and `.env`).
-   **Models and records.** MLflow keeps the trained models, the training runs and the
    drift check runs: the records in its own database and the model files in the object
    store's bucket `mlflow`. They are derived from the market data and hold no personal
    data.
-   **The prediction log.** The table `predictions` holds every forecast with its
    inputs.
-   **Secrets.** `.env` holds the EODHD key and the logins and passwords of the
    services. `.env` is never committed. `.env.example` holds only development values,
    for local use. Airflow also writes its admin password into a file inside its
    container at start.

The system holds no personal data of users or customers.

## Threat model

The system is a local tool, not a service on a network. It protects:

-   the EODHD key and the other secrets, against leaving the machine by mistake;
-   the licensed market data, against being committed, published or sent elsewhere;
-   the services, against being reachable from any other machine.

It does not guard against anyone or anything on the member's own machine: another
account, a program or a web page there ([What the product supports]). Whoever can run
code as the member, or connect to localhost (127.0.0.1), can use every service as the
member can.

[What the product supports]: docs/requirements.md#what-the-product-supports

## Trust boundaries

-   **The host and the Compose network.** Only the services listed under [Network
    exposure and transport] are published on the host. The others are reachable only
    from inside the Compose network. Inside that network the services trust one another:
    the API, the data service, MLflow and Prometheus ask for no login from a caller in
    the network.
-   **The project image and Airflow's image.** Airflow's image holds none of the
    project's packages and has no access to Docker. Its pipelines only call the data
    service and the API. Of the project's settings, Airflow receives only
    `REPLAY_INTERVAL_SECONDS` and the folder `config/`, read-only. Besides these it
    holds its own database password, its token secret (`AIRFLOW_JWT_SECRET`) and its
    admin password. It never receives the EODHD key.
-   **The web app and the API.** The web app reads everything through the API and
    touches neither the database nor MLflow. Its image holds only its own packages, and
    it runs as the unprivileged account `nobody`.
-   **The object store.** Only services inside the Compose network reach it, with the
    object store's login, which MLflow and the services built from the project image
    hold.
-   **The outside.** Calls out of the machine are listed under [Network exposure and
    transport].
-   **The link check.** The link check of `make lint` runs in a container that mounts
    the repository read-only and has no network (`--network none` in the `Makefile`),
    so it can read the checkout but send nothing.
-   **Containers.** The project image starts as the administrator account (root) and
    then switches to the account that owns the `datasets/` folder, so the files it
    writes belong to the member. No container can control Docker, because `compose.yaml`
    mounts no Docker socket. The containers keep Docker's default protections: none has
    its root file system set to read-only, and none gives up the extra privileges (Linux
    capabilities) that Docker grants by default.

[Network exposure and transport]: #network-exposure-and-transport

## Encryption at rest

Nothing is encrypted at rest. The database, the object store, Airflow's logs and
Prometheus's data live in Docker volumes on the member's disk. The dataset copies in
`datasets/` and the file `.env` lie there as plain files. The member's disk or account
encryption is the only protection.

## Authentication and authorisation

| Service | Login |
|---|---|
| API | none; every route, `/training` and `/prediction-drift-check` included, answers any caller |
| MLflow | none; its page can delete runs and models and change which model is in production |
| Web app | none |
| Airflow | one `admin` login with the password `AIRFLOW_ADMIN_PASSWORD`; the pipelines call the API and the data service without a login |
| Grafana | one `admin` login with the password `GRAFANA_ADMIN_PASSWORD` |
| PostgreSQL | the login `POSTGRES_USER`; MLflow and Airflow have logins of their own that own only their databases |
| Object store | the login `OBJECT_STORE_USER` for its S3 port; see below |

The API has no login. Unless the member changes them, Grafana and Airflow use the public
development passwords of `.env.example`, for local use only.

## Network exposure and transport

Every service is published on the host at 127.0.0.1 only, or not at all. The ports of
the database, the API, the web app, MLflow, Airflow and Grafana are set in `.env`. The
object store, the data service and Prometheus publish no port.

Traffic on the machine is not encrypted: the HTTP traffic and the PostgreSQL connections
run without TLS, on the loopback address and inside the Compose network. Calls out of
the machine use HTTPS.

Inside the Compose network, the object store's S3 port refuses anonymous requests, but
SeaweedFS's internal admin and management ports answer without a login: its admin page
(port 23646), its master (9333) and its filer (8888). Its worker's gRPC port (33646) is
unauthenticated. None of them is published on the host, but every container in the
network can reach them. MLflow additionally accepts requests only for the host names it
lists in its start command (`--allowed-hosts` in `compose.yaml`).

Calls out of the machine:

-   **EODHD.** Loads call EODHD's API over HTTPS with the member's key. EODHD requires
    the key as a parameter in the URL. The request logging of the HTTP client is
    switched off, an error names only the path of the request, and `make contract` shows
    short tracebacks that never hold the key (`src/forecasting/eodhd.py`, `Makefile`).
-   **The API's documentation pages.** `/docs` loads a script and a style sheet from
    `cdn.jsdelivr.net` and an icon from `fastapi.tiangolo.com`. `/redoc` loads a script
    from `cdn.jsdelivr.net`, an icon from `fastapi.tiangolo.com` and fonts from
    `fonts.googleapis.com` and `fonts.gstatic.com`. The pages make these calls when they
    are opened.
-   **Grafana.** At start, Grafana may download the signing keys of its plugins from
    `grafana.com`.
-   **Install and update.** Docker pulls the images, and uv downloads the locked
    packages.

No component sends usage data. Each switch is set where the code or `compose.yaml` sets
it:

| Component | Switch |
|---|---|
| SeaweedFS | the flag `-master.telemetry=false` in the `object-store` command in `compose.yaml` |
| MLflow | `MLFLOW_DISABLE_TELEMETRY` in `compose.yaml` (the project services and the `mlflow` service) and in the `Makefile` for tests and `make contract` |
| Grafana | `GF_ANALYTICS_REPORTING_ENABLED`, `GF_ANALYTICS_CHECK_FOR_UPDATES`, `GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES` and `GF_NEWS_NEWS_FEED_ENABLED` off, `GF_SECURITY_DISABLE_GRAVATAR` on and `GF_PLUGINS_PREINSTALL_AUTO_UPDATE` off in `compose.yaml` |
| Streamlit | `gatherUsageStats` off, and a fixed `serverAddress` so it asks no outside service for the machine's address, in `webapp/.streamlit/config.toml` |
| DVC | `DVC_NO_ANALYTICS` set for every DVC call in `src/forecasting/datasets.py` |
| pyright | `PYRIGHT_PYTHON_IGNORE_WARNINGS` set in the `make lint` recipe of the `Makefile`, which switches off the wrapper's check against PyPI for a newer version |
| Evidently | none needed: building a report sends none |
| Airflow, Prometheus, PostgreSQL | none: they have no usage reporting |

## Recovery

There is no backup; what is lost and what comes back is in [Backup and restore].

After a leaked secret:

-   **EODHD key.** Revoke it or create a new one at EODHD, put the new key into `.env`
    and run `docker compose up --detach --wait`, so the services that read it are
    created again.
-   **Other passwords.** Change them in `.env` and create the services again. The
    database image applies `POSTGRES_PASSWORD` only when it first creates its volume.
    Change that password inside the database as well (`make db-shell`), or run
    `make reset`, which deletes everything stored; then run `make update` and
    `make train`, as [After `make reset`] says.
-   **A committed secret** is leaked for good: replace it as above.

[After `make reset`]: DEPLOYMENT.md#after-make-reset
[Backup and restore]: DEPLOYMENT.md#backup-and-restore

## Member responsibilities

-   Keep `.env` private and out of Git, and never paste a key or password into an issue,
    a chat or a log.
-   Use only your own EODHD key and your own database. Share no price data, dataset copy
    or database dump with another person, and never commit them.
-   On a shared machine, change every development password of `.env.example` in your
    `.env`, except the database login and port that [CONTRIBUTING.md] names. The
    database then stays protected only by its public development password, so keep your
    account and your disk private, and encrypt the disk if the data matters.
-   Leave the published ports on 127.0.0.1: do not change `compose.yaml` to publish a
    service on another address, and do not expose Docker's own API.
-   Keep the packages and images current by pulling new versions of the code as
    described in [Update].
-   Follow the limits of the product when running the pipelines and the manual commands
    ([Pipelines]).

[CONTRIBUTING.md]: CONTRIBUTING.md#running-the-tests
[Pipelines]: DEPLOYMENT.md#pipelines
[Update]: DEPLOYMENT.md#update

## Known limitations

-   The API, MLflow and the web app have no login. Anyone or anything on the machine can
    start trainings, read forecasts, and change or delete models and runs.
-   Loading a model can run code: `mlflow.sklearn.load_model` loads the format the
    stored model names, and MLflow allows its pickle format as well as its safer skops
    format. Whoever can write to MLflow can therefore run code in the API, which holds
    every secret of `.env`.
-   Every secret in `.env` reaches the API container, the data service and the project
    commands, because `compose.yaml` passes the whole file to the services built from
    the project image (`env_file`). The API therefore holds the EODHD key and every
    password although it needs only some of them. The other services receive only the
    values their own service lists in `compose.yaml`; what Airflow receives is under
    [Trust boundaries].
-   Services inside the Compose network ask no login of one another, and the object
    store's internal ports are open to every container there.
-   Nothing is encrypted at rest, and traffic on the machine is not encrypted.
-   The development logins and passwords of `.env.example` are public; they protect
    nothing once copied unchanged. On a shared machine the database keeps its public
    development password, as [Member responsibilities] says.
-   The Airflow admin password is written in plain text to a file inside its container.
-   `/docs`, `/redoc` and Grafana depend on outside hosts for scripts, styles, icons,
    fonts and plugin keys.
-   There is no backup, and no check of the images beyond their pinned versions and the
    hashes in `uv.lock`.

[Member responsibilities]: #member-responsibilities
[Trust boundaries]: #trust-boundaries

## Reporting

Report a security problem privately with "Report a vulnerability" on the repository's
Security tab on GitHub. Say what you found and how to reproduce it. Never include a key,
a password or price data in the report.
