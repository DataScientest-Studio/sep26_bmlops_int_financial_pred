# Deployment

How the forecasting service is installed, configured, updated, rolled back and checked.
It runs on one machine per member, as Docker Compose services; how it is built is in
[ARCHITECTURE.md], and what it holds and who can reach it is in [SECURITY.md].

[ARCHITECTURE.md]: ARCHITECTURE.md
[SECURITY.md]: SECURITY.md

## Host

The service runs on one local machine. Nothing runs in the cloud, and no machine is
shared between members. The host provides:

-   **Docker Engine 28.0 or later** with Docker Compose (Docker Desktop includes both).
-   **uv**, which installs the Python version the project pins in `.python-version` if
    it is missing and creates the project's environment from `uv.lock`.
-   `make` and `git`. The Makefile reads the current commit from Git to record which
    code built the images.
-   **Free local ports.** The ports set in `.env` for the database (`POSTGRES_PORT`),
    the API (`API_PORT`), the web app (`WEBAPP_PORT`), MLflow (`MLFLOW_PORT`), Airflow
    (`AIRFLOW_PORT`) and Grafana (`GRAFANA_PORT`). Which services are published, and on
    which address, is in [SECURITY.md][network].
-   **Internet access**, to pull the images and packages at install and to reach EODHD
    when loading prices.
-   **An EODHD key** of the member's own; see [Install].

[Install]: #install
[network]: SECURITY.md#network-exposure-and-transport

## Install

From an empty machine to a running system:

1.  **Clone** the repository and open its folder.
1.  **Create `.env`** from the template, and keep every key of the template. A missing
    key is named when a command, the API or the data service starts.

    ```bash
    cp .env.example .env
    ```

    `.env` is never committed. Keep `POSTGRES_USER`, `POSTGRES_PASSWORD` and
    `POSTGRES_PORT` as the template has them, because the tests need them
    ([CONTRIBUTING.md]). The template's development logins are for local use only; see
    [Configure].
1.  **Get an EODHD key.** Register for the free tier at [EODHD] and follow the
    instructions there to get your key. Put it into `.env` as `EODHD_API_KEY`.
1.  **Create the Python environment** and try the key:

    ```bash
    make setup      # creates .venv with the locked packages
    make contract   # checks how EODHD delivers data with your key
    ```

    What `make contract` checks, and when it skips a check, is in [CONTRIBUTING.md]. It
    spends calls of the free tier's daily allowance; see [Data source].
1.  **Start the system.** One command starts every service, builds the images on the
    first run and returns once all services are healthy:

    ```bash
    docker compose up --detach --wait
    ```

    A start this way records the code version of the images as `unknown`. To record the
    commit, start through the `make` targets that [Starting individual services] lists.
1.  **Load the prices.** The first load takes the history from `HISTORY_START` on, as
    far back as the data source delivers it; every later load fetches only the new
    trading days:

    ```bash
    make update
    ```

1.  **Train the first models**, then ask for a forecast:

    ```bash
    make train
    make predict
    ```

    Until a security has a production model, the API refuses a forecast for it.
1.  **Switch the pipelines on**, as described next, if the system should run by itself.

[Configure]: #configure
[CONTRIBUTING.md]: CONTRIBUTING.md#running-the-tests
[Data source]: ARCHITECTURE.md#data-source
[EODHD]: https://eodhd.com
[Starting individual services]: #starting-individual-services

### Pipelines

Airflow's four pipelines start paused. Open Airflow's page at `localhost` on the port
`AIRFLOW_PORT`, log in as `admin` with the password stored under
`AIRFLOW_ADMIN_PASSWORD` in your `.env`, and switch a pipeline on with its toggle. The
pipelines are `daily_update`, `replay`, `training` and `prediction_drift_check`;
[ARCHITECTURE.md][chain] says what each does. The product's limits on them ([What the
product supports]):

-   Never switch on `daily_update` and `replay` at the same time: the daily update loads
    from EODHD, and the replay plays stored history back into a database of its own.
-   `training` and `prediction_drift_check` may be on with either of them and with each
    other.
-   Once the latest stored day is replayed, each `replay` run is skipped: switch the
    pipeline off and run `make replay-reset` to start over.
-   While `daily_update` or `replay` is on, run no manual `make update`, `make replay`
    or `make replay-reset`. While `training` is on, start no training by hand, neither
    `make train` nor a request to the API's `/training`.

[chain]: ARCHITECTURE.md#how-the-chain-fits-together
[What the product supports]: docs/requirements.md#what-the-product-supports

### Starting individual services

The `make` targets rebuild an image when its code changed, record the commit, and return
once their services answer. Each starts what it depends on. Each stop target stops only
the services named here; what is not named keeps running.

| Target | Starts | Stop with | What the stop target stops |
|---|---|---|---|
| `make db` | the database | `make db-stop` | the database; its data is kept |
| `make mlflow` | the MLflow server, with the database and the object store | `make mlflow-stop` | MLflow and the object store; the database keeps running |
| `make api` | the API, with the database and MLflow | `make api-stop` | the API |
| `make webapp` | the web app, with the API | `make webapp-stop` | the web app; the API keeps running |
| `make airflow` | Airflow, with the database, the data service and the API | `make airflow-stop` | Airflow and the data service; the database and the API keep running |
| `make monitoring` | Prometheus and Grafana, with the API | `make monitoring-stop` | Prometheus and Grafana; the API keeps running |

Where the pages are, all on this machine only: they are at `http://localhost:<port>`
with the ports `API_PORT` (the API, with its documentation at `/docs`), `WEBAPP_PORT`,
`MLFLOW_PORT`, `AIRFLOW_PORT` and `GRAFANA_PORT` from `.env`.

### Project commands

The commands below, except `make reset` and `make db-shell`, run in the project image,
rebuilt when the code changed. They start the database, the object store and MLflow
first if these are not running; nothing else needs to run. When one of the project
commands (`make update`, `make replay`, `make replay-reset`, `make train` and
`make predict`) fails, it shows its reason, never a traceback, and ends with exit
status 1. `make train` and `make predict` go through every configured security even when
one fails, print each failure at once and then fail, naming each failed security
([Invariants]).

-   `make update` (also `make load`): loads prices, splits and dividends from EODHD with
    your key. A security without stored prices is loaded from `HISTORY_START` on; for
    any other security only the new days are loaded. The command prints how many quotes
    (one day's prices of a security, see [Terms]) were stored, replaced, rejected and
    missing.
-   `make replay`: copies the next stored day into the replay database and prints the
    day replayed. The first run creates the database and fills it up to `REPLAY_START`.
    The command is refused when nothing is stored. See [Replay].
-   `make replay-reset`: deletes the replay database and the replay's records in MLflow;
    see [Backup and restore].
-   `make reset`: deletes everything stored. Afterwards run `make update` and
    `make train`; see [After `make reset`].
-   `make train`: trains a model for each configured security on its final closes and
    prints its scores next to both baselines, with whether the model was promoted or the
    production model was kept. For a security that was trained before, it first records
    a feature drift check in MLflow.
-   `make predict`: prints the production model's forecast of the next trading day for
    each configured security and stores each forecast in the table `predictions`, as the
    API's `/predict` does.
-   `make db-shell`: opens an SQL prompt in the database (`\q` leaves it).

[After `make reset`]: #after-make-reset
[Invariants]: ARCHITECTURE.md#invariants
[Terms]: ARCHITECTURE.md#terms

### Looking at the data

`make db-shell` opens an SQL prompt. For example, the latest day stored per security:

```sql
SELECT symbol, max(day) AS latest_day, count(*) AS days
FROM prices
GROUP BY symbol;
```

`db/queries/examples.sql` holds more examples. Run a file with:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/queries/examples.sql
```

To try the examples before real prices are loaded, run `db/queries/sample-data.sql` the
same way. It adds made-up prices under the symbols `AAPL.SAMPLE` and `SAP.SAMPLE`; the
suffix keeps them apart from real prices. `db/queries/remove-sample-data.sql` removes
them again; it matches only symbols that end in `.SAMPLE`, so real prices are never
deleted.

## Configure

Every value a member sets is in the table below. Each lives in one file; a setting is
named by its file and key, and this table never repeats its value. A value outside its
allowed range makes the commands and services that read it refuse to start, with a
message that names the setting. Where the allowed ranges are defined is in
[CONTRIBUTING.md][code-style]. Passwords and secrets are named by the key that holds
them and are never written elsewhere.

`.env` holds the values for the member's own machine, each explained in `.env.example`.
The other files hold the team's settings and are committed with the code.

| Setting | Lives in | What it means |
|---|---|---|
| `POSTGRES_DB` | `.env` | Name of the project database; the replay database is named after it with `_replay` |
| `POSTGRES_USER` | `.env` | Login of the project database |
| `POSTGRES_PASSWORD` | `.env` | Password of that login (secret) |
| `POSTGRES_HOST` | `.env` | Host of the database for programs run on this machine outside Docker; inside Compose it is set to the service name |
| `POSTGRES_PORT` | `.env` | Port of the database on this machine |
| `AIRFLOW_PORT` | `.env` | Port of the Airflow page on this machine |
| `AIRFLOW_ADMIN_PASSWORD` | `.env` | Password of the Airflow page's login, user `admin` (secret) |
| `AIRFLOW_DB_PASSWORD` | `.env` | Password of Airflow's own database login; letters and digits only, since it becomes part of a connection address (secret) |
| `AIRFLOW_JWT_SECRET` | `.env` | Secret Airflow signs its internal tokens with; any long random text (secret) |
| `MLFLOW_PORT` | `.env` | Port of the MLflow page on this machine |
| `MLFLOW_TRACKING_URI` | `.env` | Address of the MLflow server for programs run on this machine outside Docker; inside Compose it is set to the service name |
| `MLFLOW_DB_PASSWORD` | `.env` | Password of MLflow's own database login; letters and digits only (secret) |
| `API_PORT` | `.env` | Port of the API on this machine |
| `WEBAPP_PORT` | `.env` | Port of the web app on this machine |
| `GRAFANA_PORT` | `.env` | Port of the Grafana page on this machine |
| `GRAFANA_ADMIN_PASSWORD` | `.env` | Password of the Grafana page's login, user `admin` (secret) |
| `OBJECT_STORE_USER` | `.env` | Login of the object store that holds MLflow's model files and DVC's dataset copies |
| `OBJECT_STORE_PASSWORD` | `.env` | Password of that login (secret) |
| `REPLAY_START` | `.env` | Simulated today of the first replay run: every stored day up to it is copied at once into the replay database; it must lie between the first and the latest stored day |
| `REPLAY_INTERVAL_SECONDS` | `.env` | Seconds from the start of one replayed day to the next; the replay pipeline refuses a value outside its limits, which Airflow's page names |
| `HISTORY_START` | `.env` | First day of price history to load for a security with no stored prices; a day before the trading calendar's first day, or after today, is refused |
| `EODHD_API_KEY` | `.env` | Your own EODHD key (secret) |
| `weekdays` | `config/daily_update.toml` | Days the daily update runs on, Monday = 1 to Sunday = 7 |
| `timezone` | `config/daily_update.toml` | Time zone of the weekdays and of `start_after` |
| `start_after` | `config/daily_update.toml` | Time the final delay counts from; the daily update starts the final delay later |
| `load_limit_minutes` | `config/daily_update.toml` | Longest a load may run, in whole minutes; a scheduled daily update that has no load by then counts as missed |
| `final_delay_minutes` | `config/daily_update.toml` | Whole minutes after an exchange's close from which a fetched close is final, for every load |
| `evaluation_days` | `config/training.toml` | Latest trading days held back from training to score each model |
| `retraining_interval_days` | `config/training.toml` | Stored trading days after which a security is trained again |
| `drift_window_days` | `config/drift_checks.toml` | How many of the latest days a drift check compares with the days up to the latest training: stored trading days for the feature drift check, days with a scheduled forecast for the prediction drift check |
| `prediction_drift_check_interval_days` | `config/drift_checks.toml` | Stored trading days that must pass after a security's latest prediction drift check before the next is due |
| `drift_p_value_threshold` | `config/drift_checks.toml` | A drift check finds drift when its p-value is at or below it |
| `[[securities]]` `symbol`, `exchange` | `config/securities.toml` | The securities to load, train and forecast: ticker as the data source names it, and the MIC of its exchange |
| `[[indices]]` `symbol`, `exchange` | `config/securities.toml` | Market indices to load as reference series, never forecast; the MIC of the exchange whose calendar and close the index follows |
| `scrape_interval` | `prometheus/prometheus.yml` | How often Prometheus collects the API's numbers |
| `evaluation_interval` | `prometheus/prometheus.yml` | How often Prometheus computes the error rate |
| the range in the `rate(...)` expressions | `prometheus/rules.yml` | Window of the error rate |
| `interval` | `grafana/provisioning/alerting/alerts.yaml` | How often Grafana checks the alert rules |
| `params` | `grafana/provisioning/alerting/alerts.yaml` | Threshold of each alert rule ("API error rate", "Data not fresh", "Daily update missed") |
| `for` | `grafana/provisioning/alerting/alerts.yaml` | How long the threshold must stay crossed before each rule fires |
| `noDataState` | `grafana/provisioning/alerting/alerts.yaml` | State of each rule when it has no data to judge |
| `execErrState` | `grafana/provisioning/alerting/alerts.yaml` | State of each rule when Prometheus cannot be asked |
| `thresholds` of the "Trading days behind" panel | `grafana/dashboards/api.json` | The number of trading days behind from which the panel turns red |

The name `api:error_ratio:rate5m` carries the window of the error rate. If you change
the window, rename the rule and change the name in `grafana/dashboards/api.json` and
`grafana/provisioning/alerting/alerts.yaml`, which read it.

[code-style]: CONTRIBUTING.md#code-style

### When a change takes effect

-   Prometheus and Grafana read their files when they start: after a change, run
    `docker compose restart prometheus` or `docker compose restart grafana`. Grafana
    also picks up a changed dashboard file by itself within seconds. Change the alert
    rules and the dashboard in their files under `grafana/`, not on Grafana's page.
-   A change to a file in `config/` takes effect in the daily update pipeline when
    Airflow next reads `airflow/dags/daily_update.py`, which it does regularly; in the
    data service at its next load; in a command when it next runs; and in the API after
    `docker compose restart api`.
-   A change to `config/securities.toml` reaches the training and prediction drift check
    pipelines at their next run, since each run reads the file. They call the API, which
    knows only the securities listed when it started: until
    `docker compose restart api`, each run handles the other securities and then fails,
    naming the new one as unknown to the API.
-   A change to `.env` takes effect when the service that reads it is created again. Run
    `docker compose up --detach --wait`, which creates again every service whose
    settings changed.
-   When a service stops because a value is refused, `docker compose logs api` (or
    `docker compose logs data`) shows the reason.

## Update

There is no automatic update. To bring a machine to a newer version of the code:

1.  **Switch the pipelines off** on Airflow's page, so no run starts during the update.
2.  **Pull** the new version with `git pull`.
3.  **Check what the pull changed.** Git lists the changed files.
    -   If `db/init/` changed a table that already exists, you need `make reset`
        (step 5) and can skip the MLflow step (step 6).
    -   If the MLflow version in `uv.lock` changed, you need the MLflow step.
    -   If a file under `prometheus/` or `grafana/provisioning/` changed, run
        `docker compose restart prometheus grafana` after step 7. Compose creates a
        container again only when its settings or image changed, and both services read
        these files only when they start. Changed dashboards under `grafana/dashboards/`
        need no restart: Grafana re-reads them within seconds.
    -   If `.env.example` has a new key, copy it into your `.env` before step 7.
4.  **Install the packages** with `make setup`, if `uv.lock` or `.python-version`
    changed.
5.  **A changed table** needs `make reset`. A change to a table that already exists
    takes effect only in a database that is created again. What `make reset` deletes,
    and what to run afterwards, is in [Backup and restore]. A table that is new is
    created where it is missing at every start of the services in the member's database;
    the replay database gains it only after `make replay-reset` and the next
    `make replay`.
6.  **Upgrade MLflow's database** when the update raises the locked MLflow version. The
    MLflow server does not start against a database of an older schema until the upgrade
    has run, so run it first. With the database running (`make db`), build the new
    MLflow image with `docker compose build mlflow`, run the upgrade command below, then
    start the server with `make mlflow`. Skip this step when step 5 applies, because the
    reset deletes MLflow's database:

    ```bash
    docker compose run --rm --no-deps mlflow sh -c 'mlflow db upgrade "$MLFLOW_BACKEND_STORE_URI"'
    ```

7.  **Rebuild and restart** the services with the `make` targets. They rebuild an image
    whose code changed and record the commit. The targets `make airflow`, `make webapp`
    and `make monitoring` together start every service. Airflow migrates its own
    database when it starts.
8.  **Check the system** as described under [Health], then switch the pipelines on
    again.

No snapshot of any kind is taken before an update or a migration. Neither the database
nor the object store is copied, and an upgrade of MLflow's database cannot be undone by
the system; see [Backup and restore].

## Rollback

The previous version of the code comes back by checking it out and rebuilding:

1.  Switch the pipelines off.
1.  Check out the earlier commit with `git checkout <commit>`.
1.  Run `make setup`, then rebuild and restart with `make airflow`, `make webapp` and
    `make monitoring`. If the files under `prometheus/` or `grafana/provisioning/`
    differ between the two versions, run `docker compose restart prometheus grafana`
    afterwards.
1.  Check the system as described under [Health].

Only the code goes back. Whatever the newer version wrote stays: rows and tables in the
database, runs and models in MLflow, dataset copies and forecasts. A production model
that the newer version promoted also stays. To move the alias back, open the registered
model `forecast-<symbol>` on MLflow's page, open the earlier version and give it the
alias `production`; an alias belongs to one version, so it moves.

A newer version may have changed a table or upgraded MLflow's database. The system has
no step that undoes this, so the earlier code may not work with that data. `make reset`
then returns a consistent state and loses everything stored.

## Backup and restore

There is no backup and no restore. The system never copies its database, its object
store or its dataset copies anywhere, and no command reads a copy back. DVC pushes each
dataset copy into the object store, but that is no copy outside the member's Docker
volumes and `datasets/`.

`make reset` stops every service and deletes every Docker volume and the contents of
`datasets/` except `.gitkeep`. Lost are:

-   the prices, splits and dividends;
-   the forecasts of the prediction log;
-   the records of MLflow (runs, registered models, drift checks) and of Airflow;
-   the object store with the model files and the dataset copies;
-   the pipeline logs and the monitoring history.

`make replay-reset` deletes the replay database with its forecasts, and the replay's
runs, models and model files in MLflow. It also removes for good everything that was
deleted on MLflow's page, whether or not it came from the replay. The member's own
database and models stay. See [Replay].

### After `make reset`

Nothing is left to forecast from. Start again in this order:

1.  Run `make update`. It loads the prices, splits and dividends again, with the whole
    history the data source delivers. This load uses the day's allowance of the free
    tier.
1.  Run `make train`. It trains a model for each security and promotes it as the
    security's first model.

Until step 2 has run, the API refuses a forecast for a security that has no production
model, and the web app shows the API's reason instead of a forecast. Both commands start
the services they need (the database, the object store and MLflow). They do not start
the API, the web app, Airflow, Prometheus or Grafana, which `make reset` stopped; start
them with `docker compose up --detach --wait` or the `make` targets. Airflow's pipelines
are created again and start paused, so switch on again the ones you want. The models
come back only by training again; the forecast history and the drift records are lost
for good.

## Health

### Is it running correctly

-   **Compose.** Every service has a health check. `docker compose ps --all` shows each
    as `healthy`. The steps `db-tables`, `mlflow-database`, `airflow-database` and
    `airflow-init` run once and show as exited without an error. The command
    `docker compose up --detach --wait` and the start targets return only when their
    services are healthy.
-   **API.** `http://localhost:<API_PORT>/health` answers `ok`.
    `http://localhost:<API_PORT>/metrics` lists the numbers described under
    [Monitoring][]: `trading_days_behind` per security and index (0 means no trading day
    is behind), `daily_updates_missed` (0 means none) and the drift numbers.
-   **Grafana.** Log in as `admin` with the password stored under
    `GRAFANA_ADMIN_PASSWORD` in your `.env`, on the port `GRAFANA_PORT`. The dashboard
    "API" in the folder "Financial forecasting" shows requests, response time, error
    rate, trading days behind and the "Drift" table. The alert rules are under Alerting,
    Alert rules, in the same folder: "API error rate", "Data not fresh" and "Daily
    update missed". A firing alert is only listed there; see [Constraints].
-   **Airflow.** Each pipeline's page lists its runs, and the page lists the assets
    `prices`, `replay-prices`, `scheduled-forecasts` and `prediction-drift-found` that
    the pipelines announce. A failed run shows its reason in the log of the failed task.
    How the pipelines go on past a failed security is in [How the chain fits together].
    The full error is in `docker compose logs api` and, for loads and replays, in
    `docker compose logs data`.
-   **MLflow.** The page on `MLFLOW_PORT` lists the experiment `forecasting` and, once a
    drift check has run, the experiment `drift-checks`. It lists the registered models
    `forecast-<symbol>`, each with one version marked `production`. To find the runs
    trained on code with uncommitted changes, enter
    `tags."mlflow.source.git.dirty" = "true"` in the search box above the run list; runs
    without the tag are not listed. No page shows the tag `mlflow.source.git.dirty`
    itself. The optional column "Version" in the run list shows the first characters of
    the commit, not the model version.

[Monitoring]: ARCHITECTURE.md#monitoring

### After a host restart

`compose.yaml` sets no restart policy. After a restart of the host (or of WSL, if you
run on Windows) or of the Docker engine, no service comes back by itself. The data in
the Docker volumes survives. Start the system again with
`docker compose up --detach --wait`, or with the `make` targets, and check it as above.

Airflow keeps which pipelines were switched on in its database, so they stay as they
were. A scheduled daily update that was missed while the system was down follows the
rule in [How the chain fits together]. The alert "Daily update missed" may fire.

### When drift is found

Drift means that the latest values differ from the ones the model was trained on. How
the two checks decide is in [Drift detection].

[Drift detection]: ARCHITECTURE.md#drift-detection

#### What you see

-   In MLflow, a run in the experiment `drift-checks` (`replay-drift-checks` while the
    replay database exists). Its fields are listed under [Drift records]; the field
    `drift_found` says whether drift was found, and the report `drift_report.html` is
    attached when it was.
-   In Grafana, the table "Drift" on the dashboard "API". It has one row per security,
    with "yes" in the column "Feature drift" or "Prediction drift", and the p-value
    beside it.

[Drift records]: ARCHITECTURE.md#drift-records

#### What the system does by itself

-   A feature drift check runs before every training of a security that has been trained
    before. When it finds drift, a training request that trains only when needed trains
    that security.
-   The `prediction_drift_check` pipeline runs each time the `training` pipeline has
    made its scheduled forecasts. When a check finds drift, it announces it, and the
    `training` pipeline then trains every configured security. The promotion rule
    decides whether each new model becomes the production model; see [Better model].
-   While the pipelines are paused, the system does none of this by itself. `make train`
    still runs the feature drift check first.

[Better model]: ARCHITECTURE.md#better-model

#### What you can do

1.  **Read the drift run** in MLflow: open `drift_report.html` to see which values
    moved. Check the data before retraining: `make db-shell` shows the security's latest
    stored closes, so you can see whether a stored delivery looks wrong.
1.  **Check the training result.** A training run carries the tag `drift_check_run_id`:
    the feature drift check that ran at the start of that training request. After a
    prediction drift, find the trainings by time in the experiment `forecasting`. The
    tag `promoted` of each run tells whether its model became the production model; see
    [MLflow records]. Compare the model's scores with persistence and the mean change in
    the run's metrics.
1.  **Start a training by hand** if none has run, and only while the `training` pipeline
    is switched off. `make train` trains every configured security. To train one
    security, send a request to the API with `only_when_needed` set to `false`;
    `<SYMBOL>` is a symbol from `config/securities.toml`:

    ```bash
    API_PORT=$(grep '^API_PORT=' .env | cut -d= -f2)
    curl -X POST "http://localhost:$API_PORT/training" -H "Content-Type: application/json" \
      -d '{"symbol": "<SYMBOL>", "only_when_needed": false}'
    ```

    Every training runs its feature drift check first.
1.  **Watch for drift that persists.** The security trains again on each new trading day
    while the drift lasts ([Constraints]). If retraining does not bring the model back
    near the baselines, the model or its inputs need rethinking, which is a decision for
    a person.

[Backup and restore]: #backup-and-restore
[Constraints]: ARCHITECTURE.md#constraints
[Health]: #health
[How the chain fits together]: ARCHITECTURE.md#how-the-chain-fits-together
[MLflow records]: ARCHITECTURE.md#mlflow-records
[Replay]: ARCHITECTURE.md#replay
