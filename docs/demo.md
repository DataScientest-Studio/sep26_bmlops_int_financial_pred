# Live demo

How the team shows the system live: five minutes at the mock defense and at the
defense, which has 15 minutes of presentation, the 5-minute demo and 10 minutes
of questions. Every member speaks. Any member can prepare and run the demo from
this text alone.

The demo shows a security's forecast in the web app, then the chain running by
itself on replayed days. The replay plays stored trading days back one at a
time, as if each arrived live ([ARCHITECTURE.md](../ARCHITECTURE.md#replay)). On
each replayed day the pipelines load the new quotes, store the forecasts, check
for drift, train a security again when drift is found or its retraining interval
has passed, and promote the new model if it forecasts better. The audience
follows this in the web app, MLflow and Grafana.

Each demo step names the area whose member speaks: Data, Model or Service, as
[team.md](team.md#areas) sets them.

## Before the demo

Prepare on the day before and rehearse once with the settings the demo uses.

### Settings

Each setting is named by its file and key; the table never repeats its value.
Read the value in the file. A change to `.env` takes effect when the service
that reads it is created again ([DEPLOYMENT.md][takes-effect]).

| Setting | Lives in | What it means for the demo |
|---|---|---|
| `REPLAY_START` | `.env` | Simulated today of the first replay run: every stored day up to it is copied at once into the replay database, and the stored days after it are the ones the demo replays. It must lie between the first and the latest stored day, with more stored days after it than the demo replays. A change takes effect when the data service is created again: run `make airflow`. |
| `REPLAY_INTERVAL_SECONDS` | `.env` | Seconds from the start of one replayed day to the next. The `replay` pipeline accepts 10 to 60 (`SHORTEST_INTERVAL_SECONDS` and `LONGEST_INTERVAL_SECONDS` in `airflow/dags/replay.py`); outside these limits Airflow does not load the pipeline. A change takes effect when the Airflow services are created again: run `make airflow`. |
| `retraining_interval_days` | `config/training.toml` | Stored trading days after which a security is trained again. The replay in the demo plays at least this many days, or a security is trained again only when drift is found. The API reads the file when it starts: after a change, run `docker compose restart api`. |

Choose `REPLAY_INTERVAL_SECONDS` longer than the longest training run of a
replayed day, or the replayed days pile up before their training and drift
check runs finish; the default in `.env.example` meets this. During the
rehearsal check on Airflow's page that the runs of `training` and
`prediction_drift_check` of each replayed day succeed; if they lag behind the
replayed days, choose a longer interval.

[takes-effect]: ../DEPLOYMENT.md#when-a-change-takes-effect

### Preparation

1.  **Bring the stack up** with `REPLAY_START` and `REPLAY_INTERVAL_SECONDS` set
    in `.env` as the table above says:

    ```bash
    make webapp
    make airflow
    make monitoring
    ```

    Check as [DEPLOYMENT.md](../DEPLOYMENT.md#is-it-running-correctly)
    describes: `docker compose ps --all` shows every service as `healthy`, and
    `http://localhost:<API_PORT>/health` answers `ok`.
1.  **Pause the pipelines** if an earlier run left any switched on: open
    Airflow's page and switch `daily_update`, `replay`, `training` and
    `prediction_drift_check` off. `daily_update` stays off for the whole demo:
    never switch on `daily_update` and `replay` together
    ([DEPLOYMENT.md](../DEPLOYMENT.md#pipelines)).
1.  **Start from a fresh replay and own models.** The first command deletes the
    previous replay, so the next two use the member's own database and models:

    ```bash
    make replay-reset    # deletes the replay database and the replay records in MLflow
    make update          # loads the price history from EODHD; the first time only
    make train           # trains a model for each security; the first time only
    ```

    The replay copies the stored history, so it must be loaded. The member's own
    models are the quick fallback of [If something goes
    wrong](#if-something-goes-wrong).
1.  **Play the first replay day.** On Airflow's page switch on `training` and
    `prediction_drift_check`, then `replay`. The first `replay` run creates the
    replay database and fills it up to `REPLAY_START`; its announcement starts
    `training`, which trains the first model of every security, and `training`
    then starts `prediction_drift_check`. Switch `replay` off again as soon as
    its first run has succeeded, so that no further day arrives before the demo.
    Wait until the runs of `training` and `prediction_drift_check` have
    succeeded too.
1.  **Check the web app.** Open it and pick each security in turn: each shows a
    forecast. A security that shows a reason instead has no production model
    yet; see [If something goes wrong](#if-something-goes-wrong).
1.  **Open the tabs**, one per page, each on the port the member's `.env` sets:

    | Tab | Address | Login | Open on |
    |---|---|---|---|
    | Web app | `http://localhost:<WEBAPP_PORT>` | none | the first security |
    | Airflow | `http://localhost:<AIRFLOW_PORT>` | `admin`, password `AIRFLOW_ADMIN_PASSWORD` in `.env` | the page of the `replay` pipeline |
    | MLflow | `http://localhost:<MLFLOW_PORT>` | none | the list of experiments |
    | Grafana | `http://localhost:<GRAFANA_PORT>` | `admin`, password `GRAFANA_ADMIN_PASSWORD` in `.env` | the dashboard "API" in the folder "Financial forecasting" |

## The demo

The steps take five minutes together. Steps 1 to 4 happen while the replay runs;
start step 5 once the experiment of step 3 shows a new training run of the
security chosen in step 2.

1.  **The replay starts (Data, about one minute).** In the Airflow tab switch
    `replay` on. Say that the replay copies the next stored day into a database
    of its own and makes no call to EODHD. On the pages of the pipelines show
    the chain: each `replay` run is followed by a `training` run, which trains a
    security when it has no model, when its data drifted or when its retraining
    interval has passed, and makes the day's forecast of every security; that
    run is followed by a `prediction_drift_check` run. A failed task shows its
    reason in its log.
1.  **The forecast (Service, about one minute).** In the web app tab, show:
    -   the notice at the top, "These forecasts are not investment advice.",
        which every page carries, and the title "Next-trading-day forecast";
    -   the selection box "Security": pick one security;
    -   the line chart of its closes over the latest 60 trading days, with a
        second line, "Forecast close", on the days with a forecast, and below
        it the subheader "Forecast errors": the model's and persistence's
        forecast change minus the actual change, in percentage points;
    -   the section "Forecast for" followed by the day it is for, with the close
        it starts from and the time that close was fetched, and the table of
        three forecasters, "Model version" and its number, "Persistence" (no
        change) and "Mean change", each with the change and the close it leads
        to. Say that every model is compared with both baselines and that
        beating them is not expected;
    -   the section "Model results": the model's and both baselines' scores on
        the evaluation days of the model's training run, with the columns `mae`,
        `skill` and `directional_accuracy`.
1.  **Training and promotion (Model, about one and a half minutes).** In the
    MLflow tab:
    -   open the experiment `replay-forecasting`: it holds one run per training.
        Open a run and show its parameters, its metrics `model_mae`,
        `persistence_mae` and `mean_change_mae` (with the matching `_skill` and
        `_directional_accuracy` metrics) and its tag `promoted`, which says
        whether the model became the production model;
    -   open the registered model `replay-forecast-<symbol>` of the security
        chosen in step 2: each training is a new version, and the version with
        the alias `production` is the one the API forecasts with. A new version
        gets the alias only if its error on the evaluation days is lower than
        the production model's; otherwise the tag `promoted` of its run is
        `false` and the production model stays.
1.  **Drift checks (Model and Service, about one minute).** Before each training
    of a security that was trained before, a feature drift check runs.
    -   In MLflow open the experiment `replay-drift-checks`: each run carries
        the tags `symbol` and `drift_kind`, the metrics `drift_found` (1 or 0)
        and `drift_p_value`, and, when drift was found, the report
        `drift_report.html`.
    -   In the Grafana tab, the table "Drift" has one row per security, with the
        columns "Security", "Feature drift" ("yes" or "no") and "Feature
        p-value". The dashboard refreshes itself; reload the page to see a
        change at once.
    -   The columns "Prediction drift" and "Prediction p-value" show no values
        in this demo: a prediction drift check needs as many days with a
        scheduled forecast as `drift_window_days` in `config/drift_checks.toml`
        says, more than the demo replays.
    -   Leave the panel "Trading days behind" out: it measures the member's own
        database, not the replay. The panel "Requests per second" shows the
        calls the pipelines and the web app make to the API.
1.  **The new model in the web app (Service, about half a minute).** Back in the
    web app tab, reload the page and pick the same security as in step 2. The
    heading "Forecast for" names a later day, and "From the close" a later
    close. The table names the model version: after a promotion it is the new
    version, and the "Model results" are those of the new model; without one it
    is the version from step 2, which is the promotion rule at work. Close with
    the notice: the forecasts are not investment advice.

## If something goes wrong

-   **The web app shows a reason in a box instead of a forecast**, or "The API
    could not answer" with a reason. Read the reason. A security without a
    production model has no successful `training` run yet: open the run on
    Airflow's page and read the log of its failed task; the full error is in
    `docker compose logs api`. While `training` is on, start no training by
    hand, neither `make train` nor a request to `/training`.
-   **The web app does not load.** `docker compose ps --all` shows which service
    is not `healthy`; `http://localhost:<API_PORT>/health` must answer `ok`.
    Start what is missing with `make webapp`, `make airflow` or
    `make monitoring`; Airflow keeps which pipelines were on. After a restart of
    the host or of Docker no service comes back by itself
    ([DEPLOYMENT.md](../DEPLOYMENT.md#after-a-host-restart)).
-   **No new `replay` run starts.** Check that the `replay` toggle is on. A
    `replay` run that is skipped means every stored day has been replayed:
    switch `replay` off. If Airflow's page lists an import error for `replay`,
    `REPLAY_INTERVAL_SECONDS` is outside its limits.
-   **A `training` or `prediction_drift_check` run failed.** The failed task's
    log names each security that failed and its reason; the run goes on past a
    failed security. The full error is in `docker compose logs api`, and for the
    `replay` pipeline in `docker compose logs data`.
-   **MLflow lacks an experiment.** `replay-forecasting` exists once a training
    ran while the replay database exists; `replay-drift-checks` exists from the
    second replayed day on, because a feature drift check runs only before the
    training of a security that was trained before. If the MLflow page does not
    answer, run `make mlflow`.
-   **Grafana shows no values in "Drift".** The table has values only after a
    check finished, and Prometheus collects the API's numbers at the interval
    that `scrape_interval` sets in `prometheus/prometheus.yml`.
    `http://localhost:<API_PORT>/metrics` lists the numbers `drift_found` and
    `drift_p_value`. If the Grafana page itself does not answer, run
    `make monitoring`.
-   **Nothing can be repaired in time.** Switch `replay`, `training` and
    `prediction_drift_check` off, run `make replay-reset` and reload the web app
    tab: the web app shows the forecasts of the member's own database and models
    at once, and the replay is told instead of shown.

## After the demo

Switch `replay`, `training` and `prediction_drift_check` off on Airflow's page,
so that no run starts when nobody watches. The replay and its records in MLflow
stay for anyone who wants to look at them; the next [preparation](#preparation)
deletes them with `make replay-reset`. While the replay database exists,
`make train` and the forecasts use it; `make replay-reset`, run with the
pipelines off, returns them to the member's own database and models. The
services may keep running; [DEPLOYMENT.md][stopping] lists how to stop each.

[stopping]: ../DEPLOYMENT.md#starting-individual-services
