# Financial forecasting — project plan

This plan holds the team's decisions, the decision proposals, the roadmap and the phase
plans.

Reference material: [`references/`] (index in [`references/README.md`]).

[`references/`]: ../references/
[`references/README.md`]: ../references/README.md

## Decisions

Settled. Basis: coach feedback, agreed, or built and in use. Longer explanations follow
the table.

| Topic | Decision | Basis | Date | Details |
|---|---|---|---|---|
| Database | PostgreSQL | Coach feedback (PostgreSQL), agreed (private databases) | Oct 12, 2026 1) | [Database](#database), [database decision](decisions/database.md) |
| Environment | uv | Coach feedback | Oct 12, 2026 1) | [DEPLOYMENT.md](../DEPLOYMENT.md) |
| Team repo | the course repo `DataScientest-Studio/sep26_bmlops_int_financial_pred` | Coach feedback | Oct 12, 2026 1) | — |
| API access | optional, phase 2: HTTP basic authentication | Agreed | Oct 12, 2026 1) | [API access](#api-access), [password hashing decision](decisions/password-hashing.md) |
| Trading calendar | the `exchange_calendars` package | Built | Oct 12, 2026 1) | [trading calendar decision](decisions/trading-calendar.md) |
| Test strategy | acceptance tests per requirement first, unit tests with the code | Built | Oct 12, 2026 1) | [Test strategy](../ARCHITECTURE.md#test-strategy), [Running the tests](../CONTRIBUTING.md#running-the-tests) |
| Requirements | StrictDoc, top level only | Built | Oct 12, 2026 1) | — |
| Continuous integration | every push runs `make lint` and `make test` on GitHub | Built | Oct 12, 2026 1) | [The checks CI runs](../CONTRIBUTING.md#the-checks-ci-runs) |
| Data source | EODHD, free tier | Agreed | Oct 12, 2026 1) | [Data source](../ARCHITECTURE.md#data-source) |
| Close prices | prices stored as they printed | Agreed | Oct 12, 2026 1) | [Close prices](../ARCHITECTURE.md#close-prices) |
| Model inputs | the model's inputs and target are built from closes corrected for splits | Decided (Tobias) | Nov 5, 2026 9) | [Close prices](../ARCHITECTURE.md#close-prices) |
| Model choice | one model per security, StandardScaler + LinearRegression (scikit-learn) | Built | Nov 5, 2026 9) | REQ-MOD-001–003, [regressor decision](decisions/regressors.md) |
| Better model | a new model replaces a security's production model only if its MAE is lower | Built | Nov 5, 2026 9) | REQ-MOD-005, [Better model](../ARCHITECTURE.md#better-model) |
| Package and login | Python package `forecasting` | Built | Oct 12, 2026 1) | — |
| Model serving | FastAPI; BentoML is not used | Coach feedback | Oct 15, 2026 2) | — |
| Web app | Streamlit | Decided (Tobias) | Nov 7, 2026 10) | REQ-APP-001–003 |
| Roadmap | milestones and phase plans as written in this plan | Decided (Tobias) | Oct 19, 2026 3) | [Roadmap](#roadmap) |
| Reference securities | six stocks and two market indices, as configured in `config/securities.toml` | Decided (Tobias) | Oct 19, 2026 3) | [Reference securities](../ARCHITECTURE.md#reference-securities) |
| Objectives and key metrics | as drafted in `docs/requirements.sdoc` | Decided (Tobias) | Oct 19, 2026 3) | [Objectives](requirements.md#objectives), [Key metrics](requirements.md#key-metrics) |
| Local operation | each member runs the whole system on their own machine; no cloud service | Decided (Tobias) | Oct 19, 2026 3) | [What the product supports](requirements.md#what-the-product-supports) |
| Replay | replays into a database of its own, one trading day per interval in seconds (a setting) | Decided (Tobias) | Oct 22, 2026 5) | REQ-DAT-003 |
| Dataset versions | a dataset version is a DVC record of a training dataset | Decided (Tobias); DVC optional (coach), kept: Decided (Tobias) | Oct 19, 2026 3), Oct 22, 2026 5), Oct 22, 2026 6) | REQ-CON-003, [Dataset versions](../ARCHITECTURE.md#dataset-versions), [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) item 5 |
| Airflow | Airflow 3.3.2 with the LocalExecutor | Decided (Tobias) | Oct 21, 2026 4) | [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) |
| Code review | work from a member's own branch reaches `main` through a pull request | Decided (Tobias) | Oct 21, 2026 4) | [Proposing and reviewing a change](../CONTRIBUTING.md#proposing-and-reviewing-a-change) |
| Provisional closes | a price fetched while its session runs stands in for the close | Built | Oct 22, 2026 5) | [Provisional closes](../ARCHITECTURE.md#provisional-closes), REQ-DAT-007 |
| Scope | level 1 complete with several securities | Decided (Tobias) | Oct 22, 2026 5) | [Roadmap](#roadmap) |
| History to train on | training uses every stored final day of a security | Decided (Tobias) | Oct 22, 2026 5) | [Data source](../ARCHITECTURE.md#data-source) |
| Code files | separate modules for features, training, evaluation and prediction in `src/forecasting/` | Built | Oct 22, 2026 5) | — |
| Model store | MLflow's model registry keeps the models | Coach feedback (registry, PostgreSQL, separate object store); Decided (Tobias) (SeaweedFS) | Oct 22, 2026 6) | [Object store](../ARCHITECTURE.md#object-store), [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) item 3 |
| Monitoring | Evidently for drift; Prometheus and Grafana for the metrics and the dashboard, API usage included | Coach feedback | Oct 22, 2026 6) | REQ-MON-001–005 |
| Versioning | every training run records the model, the version of the dataset it trained on and the commit of the code it ran | Coach feedback | Oct 22, 2026 6) | REQ-MOD-004, [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) items 3 and 5 |
| Drift reports | each drift check is a separate MLflow run | Decided (Tobias) | Nov 2, 2026 7), Nov 9, 2026 11) | REQ-MON-001–002 |
| Training when needed | a security is trained only when needed | Decided (Tobias) | Nov 9, 2026 11) | REQ-MOD-006, REQ-MON-001–002 |
| Daily update schedule | the schedule and the final delay are team configuration in `config/daily_update.toml` | Decided (Tobias) | Nov 4, 2026 8) | [Provisional closes](../ARCHITECTURE.md#provisional-closes) (final delay), [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) (schedule settings) |
| Settings checks | configured values are checked when the API, the data service or a command starts | Decided (Tobias) | Nov 4, 2026 8) | REQ-AUT-007 |

1\) As presented: sep26_bmlops_int_financial_pred @ Mon Oct 12, 2026 12pm - 12:30pm
(CEST).

2\) Coach answer in the team Slack channel, Oct 15, 2026.

3\) Decided by Tobias as coordinator, Oct 19, 2026.

4\) Decided by Tobias as coordinator, Oct 21, 2026.

5\) Decided by Tobias as coordinator, Oct 22, 2026.

6\) Coach meeting, Oct 22, 2026; the choices the coach left to us decided by Tobias as
coordinator, Oct 22, 2026.

7\) Decided by Tobias as coordinator, Nov 2, 2026.

8\) Decided by Tobias as coordinator, Nov 4, 2026.

9\) Decided by Tobias as coordinator, Nov 5, 2026: the model's inputs, corrected for
splits; the model choice and the better-model rule, as built.

10\) Decided by Tobias as coordinator, Nov 7, 2026.

11\) Decided by Tobias as coordinator, Nov 9, 2026.

### Details of the decisions

The table states each decision in one clause. The rest of each decision follows here.

-   **Database**: each member's database is private and filled only from EODHD with
    their own key (see [Database]).
-   **Environment**: `make setup` installs the locked packages.
-   **Team repo**: with this project's full history and its own structure.
-   **API access**: against a `users` table, passwords as bcrypt hashes, roles `user`
    and `admin` (see [API access]).
-   **Trading calendar**: wrapped in one module of the project.
-   **Test strategy**: pytest with pytest-xdist.
-   **Requirements**: no nested requirements; source `docs/requirements.sdoc`,
    `make requirements` regenerates `docs/requirements.md` after every change.
-   **Data source**: (20 calls per day, 1 year of history); each member uses their own
    free key; `make load` fills a new database, `make update` adds the new trading days.
-   **Close prices**: splits and dividends in tables of their own.
-   **Model inputs**: not for dividends; volumes, which the model does not use, are
    corrected for splits too.
-   **Model choice**: predicting the next trading day's change from the 5 past daily
    changes; scored on the latest evaluation days, which training holds back, against
    the persistence and mean-change baselines by MAE, skill against persistence and
    directional accuracy.
-   **Better model**: the MAE is measured on the latest evaluation days
    (`evaluation_days` in `config/training.toml`) and compared with the production
    model's on the same days; a tie keeps the production model; a security's first model
    always becomes its production model.
-   **Package and login**: development login `admin`/`admin` in `.env.example`, for
    local use only.
-   **Web app**: in a service of its own that reads everything through the API.
-   **Dataset versions**: never the store training reads from; DVC runs without Git and
    keeps every dataset version on the member's own machine, in DVC's own store and in
    the local object store.
-   **Airflow**: its own database on the project's PostgreSQL server; each task calls a
    service built from the project image: training through the API, loads and replay
    through a data service reachable only inside Compose.
-   **Code review**: an approval is not required yet.
-   **Provisional closes**: until a later fetch replaces it; it is final once fetched a
    set delay after its exchange's close.
-   **Scope**: level 1 means the full chain, persistence and mean-change baselines,
    historical replay and trading calendar; plus the level 3 parts the course requires
    (prediction logging, drift checks, triggered retraining, keep-the-better-model
    rule); level 2 items (more securities, backtesting) only if the chain is complete by
    Nov 6.
-   **History to train on**: how far back that reaches depends on each member's key and
    database, so it may differ from machine to machine.
-   **Model store**: the MLflow server keeps its records in a database of its own on the
    project's PostgreSQL server and the model files in a local S3-compatible object
    store, SeaweedFS.
-   **Versioning**: or `unknown` for an image `make` did not build.
-   **Drift reports**: in the experiment `drift-checks`, or `replay-drift-checks` while
    the replay database exists; no Evidently UI (can be added later).
-   **Training when needed**: it has no recorded training, the feature drift check
    (REQ-MON-001) finds drift, or at least `retraining_interval_days`
    (`config/training.toml`) trading days have been stored since its latest training;
    when drift is found in the forecasts, every configured security is trained;
    `make train` always trains.
-   **Daily update schedule**: read by the pipeline and the API.
-   **Settings checks**: a missing or out-of-range value stops that start with a message
    naming the setting; `make contract` checks each stock's exchange against EODHD's
    list of exchanges.

[API access]: #api-access
[Database]: #database

### Database

PostgreSQL, details in the [database decision]. Each member runs their own private
database, filled only from EODHD with their own key: `make update` loads the history
first and then every trading day. Price data never leaves a member's machine and is
never committed.

[database decision]: decisions/database.md

### API access

Planned, not built: the API has no login, and every route answers any caller on the
member's own machine. The decision is HTTP basic authentication against a `users` table
in the project database (passwords stored as bcrypt hashes, see the [password hashing
decision]; role `user` or `admin`). Users call `predict/` and the routes that list the
securities and return their price history and model results; admins also call
`training/` and a few user-management endpoints (add, list, remove). The web app logs in
as a user. Builds on the course's API security exercise.

[password hashing decision]: decisions/password-hashing.md

## Decision proposals

To be decided by the team.

-   Secured entry point (phase 3, after the required phase 3 items; the kick-off deck
    lists "Secured APIs" and "light scalability" for phase 3, the coach lists API
    security as optional): Nginx in front of the API and the web app as the only
    published entry point, with HTTPS (self-signed certificate, since the system runs
    locally), rate limits on `predict/` and `training/`, and requests spread over
    several API instances. Alternatives:
    -   Nginx in front (proposed): encrypts the basic-auth password on the way, stops
        request floods and shows simple scaling, all with one component; one more
        service and a certificate to manage.
    -   HTTPS in the API server itself (Uvicorn): encryption only; no rate limits or
        scaling, and each service needs its own certificate.
    -   Access control only (REQ-SVC-004), no encryption: no extra work; enough while
        everything runs on one machine (REQ-CON-002), but the password travels readable
        over any network.

## Roadmap

Team setup and areas: [team.md].

Target application, as the jury sees it at the defense: a web app that calls the model
API (see the decision "Web app" in [Decisions]).

-   Pick a security; see its next-trading-day forecast with the model version, next to
    both baselines; the "not investment advice" notice always visible.
-   A history chart of past forecasts against the actual outcomes.
-   A status panel: latest stored quote, latest training run, current production model,
    latest drift check.

Live demo: replay advances the simulated calendar by a few trading days and the chain
runs on its own — new quotes are loaded, forecasts stored, drift checked, the model
retrained when drift is found or the retraining interval has passed, and the new model
promoted if it is better — visible in the app, MLflow and Grafana.

| Period | Milestone | Content |
|---|---|---|
| until Mon Oct 12 (coach meeting 12:00) | Foundations: a clone plus `make` gives a database with history, a trained baseline and an API answering `predict/` | "Phase 1 plan" below; roadmap and team setup agreed |
| Oct 13–22 (coach meeting) | Phase 1 finished and the first phase 2 piece | open items of the "Phase 1 plan"; the agreed "Phase 2 plan" |
| Oct 23–29 | Chain runs end to end: one replayed day goes from new quotes through training and promotion to the API serving the new model | items in "Phase 2 plan" |
| Oct 30–Nov 6 | Closed loop and monitoring | items in "Phase 3 plan" |
| Nov 7–11 | Feature freeze Nov 11 | tests, README and API docs, check from a fresh clone, demo script |
| Thu Nov 12 | Mock defense call | full demo as at the defense |
| Nov 13–15 | Polish | fixes from the mock defense, presentation (slides or in the web app) |
| Mon Nov 16 | Coach meeting: phase 3 check | full demo; the coach's findings become the fix list |
| Nov 17–22 | Fix and rehearse | fixes from the coach meeting, 1–2 rehearsals with equal speaking time |
| about Mon Nov 23 | Defense | one week after the coach meeting; the exact day is set by the coach |

### Contents of the build milestones

-   Oct 23–29: MLflow tracking and registry, "better model" rule, Docker Compose
    services (database, API, object store, MLflow, Airflow), Airflow DAGs for ingestion
    and training, replay and trading calendar, DVC dataset versions with hashes and the
    code's commit in MLflow.
-   Oct 30–Nov 6: prediction log and outcome collection, Evidently drift checks (one
    before each training, one in a pipeline that checks the forecasts), Prometheus and
    Grafana with API usage, alerts and the retraining webhook, first web app version.

Level 2 items (more securities, backtesting) start only if the chain is complete by
Nov 6.

## Phase 1 plan — foundations by Mon Oct 12

Proposal for the team. Coach meeting Mon Oct 12, 12:00 (invite sent; a time that does
not suit is moved on request in Slack).

Goal: a teammate runs `git clone` and a handful of `make` commands and gets a running
database with price history, a trained baseline model, and an API answering `predict/`.

Each item lists what makes it done; a ticked box is done, an open box is still to do.
Depends on: in brackets.

-   [x] **0 Team meeting** (before Oct 12; held Oct 11)
    -   [x] roadmap decided (Tobias, Oct 19)
    -   [x] organisational setup settled over the course of the project: one member
        handles the model; work is not assigned task by task
    -   [x] database and data source decided
    -   [x] securities decided (Tobias, Oct 19; see [Reference securities])
    -   [x] objectives and key metrics (`docs/requirements.sdoc`) decided (Tobias,
        Oct 19)
-   [x] **1 Repo ready and shared** (0)
    -   [x] every member invited to write access; closed (Tobias, Oct 19)
    -   [x] own repo structure (coach feedback, see [Decisions], note 1)
    -   [x] template README replaced
    -   [x] `.gitignore` and `.env.example` in place
    -   [x] CI passes (see [The checks CI runs])
-   [x] **2 Reproducible environment** (1)
    -   [x] `pyproject.toml`, `uv.lock`, `.python-version`; works from a fresh clone
    -   [x] Makefile targets `setup`, `db`, `load`, `update`, `api`, `test`
    -   [x] Makefile targets `train`, `predict`, run in the project image like the other
        commands; trained models are stored in MLflow (Phase 2, item 3)
-   [x] **3 PostgreSQL** (2): Compose file with only the database (exact image tag, data
    volume, credentials from `.env`); table `prices` keyed by (security, day)
-   [x] **4 One-time load script** (3, data source): loads the history of the agreed
    securities; a re-run creates no duplicates; API key read from `.env`
-   [x] **5 Baseline training pipeline** (3; 4 for real data)
    -   [x] `read_prices` reads the stored prices of one security
    -   [x] a training function builds the target (next-day change), trains, compares
        with the persistence and mean-change baselines, registers the model in MLflow
    -   [x] a prediction function returns the next-day forecast for one security
    -   [x] unit tests for feature building
    -   [x] the acceptance tests of REQ-MOD-001–003 pass
-   [x] **6 Initial API endpoints** (5)
    -   [x] FastAPI routes `training/` (runs training) and `predict/` (security in;
        forecast and model version out), wired to the training and prediction functions;
        unknown symbols refused
    -   [x] the acceptance tests of REQ-SVC-001/002 pass
-   [x] **7 Minimum tests and docs** (2–6)
    -   [x] setup instructions for a fresh clone (`DEPLOYMENT.md`)
    -   [x] unit tests run in parallel with pytest-xdist; both endpoints covered by the
        acceptance tests of REQ-SVC-001/002

Repo sharing (item 1): every member works with their own GitHub account; access is
granted to the accounts, never shared. Each member brings their GitHub username to the
meeting.

-   Team repo: the course repo `DataScientest-Studio/sep26_bmlops_int_financial_pred`,
    holding this project's full history. Members get write access by invitation from an
    admin of the repo.
-   A ruleset on `main` refuses deleting it and force pushes; GitHub enforces it because
    the course repo is public. How changes reach `main`: [Proposing and reviewing a
    change].

Interfaces to agree at the meeting, so items 3–6 can be built in parallel:

-   Table: `prices(symbol, day, open, high, low, close, volume, fetched_at)`, primary
    key (symbol, day); `fetched_at` is the time the row was fetched (UTC), see
    [Provisional closes].
-   Tables: `splits(symbol, day, ratio)` and `dividends(symbol, day, amount, currency)`,
    primary key (symbol, day) each.
-   Functions: `train(engine, settings, symbol)`, which returns the training result with
    the model version, and `predict(engine, settings, symbol)`, which returns the
    forecast.
-   API: request and response of `training/` and `predict/`.

Split: by area (data, model, service), see [team.md].

Trained models are recorded in MLflow (Phase 2, item 3).

[Proposing and reviewing a change]: ../CONTRIBUTING.md#proposing-and-reviewing-a-change
[Provisional closes]: ../ARCHITECTURE.md#provisional-closes
[Reference securities]: ../ARCHITECTURE.md#reference-securities
[The checks CI runs]: ../CONTRIBUTING.md#the-checks-ci-runs

## Phase 2 plan — the chain runs end to end

Coach meeting Thu Oct 22 (a progress check, not a submission): phase 1 finished and the
first piece below. The chain is complete by Oct 29.

Goal: Airflow starts the chain on a schedule and it runs with no manual step — new
quotes (in a demo: replayed history) reach the database, a model is trained on them,
MLflow records the run, the new model is promoted if it beats the production model, and
the API serves the production model. `docker compose up` starts all of it.

Course checklist for this phase ([course checklist]): MLflow tracking and model
registry; compare each new run with the previous model and tag the best; Docker
microservices with Compose; scheduled training (Airflow recommended); DVC without Git,
dataset hashes stored in MLflow. Optional: unit tests and CI, API security, Kubernetes.

Each item is one complete piece that fits the interfaces below; it is merged only when
it works. Depends on: in brackets.

-   [x] **1 Phase 1 finished**: the open boxes of the Phase 1 plan; every acceptance
    test of phase 1 passes. Blocks items 3 and 4 and the training pipeline of item 7;
    the other items need no trained model.
-   [x] **2 Project image and `api` service** (REQ-AUT-003, REQ-AUT-005, REQ-AUT-006)
    -   [x] one image holds the project's code and its locked packages; the commands run
        from it
    -   [x] Compose runs the API from it next to the database; the commands and the API
        share the `datasets/` folder and the MLflow server
    -   [x] paths (securities file, `db/init`) do not depend on the folder a command
        starts in
-   [x] **3 MLflow tracking** (2; 1 for training runs; REQ-MOD-004)
    -   [x] the object store, SeaweedFS, in Compose: an exact image version, its data in
        a volume, no published port
    -   [x] the MLflow server in Compose: its records in the database `mlflow` on the
        project's PostgreSQL server, its model files in the object store, its page on
        `127.0.0.1:${MLFLOW_PORT}`; the API and the commands reach it inside Compose
    -   [x] the project image carries the commit it was built from: `make` passes it in
        when it builds the image, a build from a tree with uncommitted changes says so,
        and a build `make` did not start records the commit as `unknown` and leaves out
        whether tracked files had uncommitted changes
    -   [x] every training run records its parameters, metrics, dataset version, code
        version, model and whether it was promoted (1)
    -   [x] MLflow is the model store; the `models/` folder is removed (1)
-   [x] **4 Registry and promotion** (3; REQ-MOD-005, REQ-SVC-001/002)
    -   [x] one registered model per security
    -   [x] a new model becomes production only if it is better by the rule in [Better
        model]; the first model always becomes production
    -   [x] `predict/` uses the production model; the training response says whether the
        model was promoted
-   [x] **5 Dataset version** (3 for the MLflow record; REQ-DAT-006)
    -   [x] `dataset_version` writes the rows it is given, without row numbers, to
        `datasets/<symbol>.csv`, records the file with DVC without Git and returns DVC's
        fingerprint of it as the version id; the same rows always get the same id, in
        the member's own database and in the replay database alike
    -   [x] before training a security, training passes the final rows it reads
        (training and evaluation days) to `dataset_version`
    -   [x] each distinct dataset is kept as a full copy in DVC's store on the member's
        own machine, so a dataset can be brought back by its id; no remote outside the
        member's own machine (price data never leaves it); DVC's own clean-up is never
        run, since without Git it would remove older copies, and only `make reset`
        deletes the copies with everything else stored; the dataset version is a record,
        training reads from the database
    -   [x] DVC copies each dataset version into the object store (item 3)
    -   [x] MLflow records it with the run
-   [x] **6 Replay** (7 for the interval; REQ-DAT-003)
    -   [x] `make replay` copies the next day from the member's own database into a
        database of its own, named after it with `_replay`: prices with their fetch
        times, splits and dividends, unchanged; the next day is the first stored day
        after the replay database's latest day; each run copies the replay database's
        latest day again, so a final quote replaces a provisional one, and copies all or
        nothing; the replay database's latest day is the simulated today
    -   [x] the first run creates the replay database and fills it up to `REPLAY_START`
        (between the first and the latest stored day); at the latest stored day there is
        nothing left to replay; `make replay-reset` deletes the replay database, so the
        next run starts over from `REPLAY_START`; with nothing stored, replay is refused
    -   [x] the member's own database is only read; replay makes no EODHD calls
    -   [x] the replay interval (`REPLAY_INTERVAL_SECONDS`, within the limits of
        REQ-DAT-003) sets the schedule of the replay pipeline (item 7)
-   [x] **7 Airflow** (2; 4 for training; 6 for replay; REQ-AUT-001, REQ-DAT-003)
    -   [x] Airflow in Compose, LocalExecutor, with its own database `airflow` on the
        project's PostgreSQL server, created when missing, and its own login, which owns
        only that database; its page on `127.0.0.1:${AIRFLOW_PORT}`, with a login for
        one admin user, whose password is set in `.env`
    -   [x] each task calls a service built from the project image over the Compose
        network, so Airflow's own image holds none of the project's packages and needs
        no access to Docker; of the project's settings Airflow receives only
        `REPLAY_INTERVAL_SECONDS` and the folder `config/` (read-only), besides its own
        database password, token secret and admin password, and never the EODHD key
    -   [x] data service: `POST /load` runs the load and answers with its report,
        `POST /replay` copies the next day and answers with it (none when nothing is
        left); reachable only inside Compose
    -   [x] daily update pipeline: one load on the days and at the time that
        `config/daily_update.toml` sets (`start_after` plus `final_delay_minutes`);
        never retried, since one load uses the free tier's day
    -   [x] replay pipeline: one replayed day every `REPLAY_INTERVAL_SECONDS` seconds
    -   [x] both pipelines start paused, the member unpauses one of them; neither
        catches up on missed runs, and each runs once at a time
    -   [x] both pipelines announce their work: the daily update pipeline after each
        load as the asset `prices`, also after one that found no new trading day; the
        replay pipeline after each replayed day as the asset `replay-prices`; a skipped
        or failed run announces nothing
    -   [x] training pipeline: starts on either `prices` or `replay-prices` (at most one
        run at a time, no catch-up, starts paused) and calls `POST /training` on the API
        for each configured security (`airflow-scheduler` depends on `api`, so
        `make airflow` starts the API too). While the replay database exists, training,
        `predict/` and the commands read the replay database instead of the member's own
        and keep replay runs and models under `replay-` names in MLflow (for example
        `replay-forecast-AAPL.US`); `make replay-reset` deletes the replay database and
        the `replay-` records in MLflow, returning the system to the member's own
        database and models. Phase 3 item 5 extends this pipeline: it also starts when
        the Airflow asset `prediction-drift-found` is updated; a run started that way
        trains every configured security, any other run trains only when needed
        (REQ-MOD-006); after training it makes one forecast per configured security and
        updates the asset `scheduled-forecasts`
-   [x] **8 Acceptance tests of phase 2**: written before the code of each item, for
    REQ-DAT-003, REQ-DAT-006, REQ-MOD-004, REQ-MOD-005 and REQ-AUT-005

Optional and not built: API access (REQ-SVC-004) and the scheduled CI checks of
REQ-AUT-004. Only the workflow that runs on every push exists; the nightly workflow that
builds the project image and runs the acceptance tests is planned.

Interfaces to agree first, so items 2–7 can be built in parallel:

-   Commands: `load` (`make load` and `make update`), `replay`, `replay-reset`, `train`
    (each `python -m forecasting.commands <name>` run in the project image, and a `make`
    target); Airflow calls the same functions through the services: `load` and `replay`
    through the data service, `train` through `POST /training` on the API. Promotion
    runs inside `train`.
-   Registered model names: one per security, `forecast-<symbol>` (for example
    `forecast-AAPL.US`), and `replay-forecast-<symbol>` while the replay database
    exists; `make replay-reset` removes the `replay-` models and runs.
-   Assets: `prices` (after each load of the member's own database), `replay-prices`
    (after each replayed day in the replay database).
-   Functions: `dataset_version(settings, symbol, rows) -> version id`, called by
    training with the final rows it reads, before it trains; MLflow records the id with
    the run.
-   Settings: MLflow page port (`MLFLOW_PORT`), replay interval
    (`REPLAY_INTERVAL_SECONDS`), Airflow page port (`AIRFLOW_PORT`). The evaluation days
    (`evaluation_days`) are set in `config/training.toml`. The daily update's days
    (`weekdays`), time zone (`timezone`), the time the final delay counts from
    (`start_after`) and load limit (`load_limit_minutes`), and the final delay
    (`final_delay_minutes`), are set in `config/daily_update.toml`.
-   Code version: the commit the project image was built from, and whether tracked files
    had uncommitted changes; when `make` did not build it, the commit is `unknown` and
    the uncommitted-changes flag is left out.

[Better model]: ../ARCHITECTURE.md#better-model
[course checklist]: ../references/course-checklist.md

## Phase 3 plan — the loop closes and is monitored

The milestone "Closed loop and monitoring" of the roadmap (Oct 30–Nov 6).

Goal: the running system watches itself. Every forecast is stored and later compared
with the actual price, drift in the data starts retraining, the API's use and the
freshness of the data are on a dashboard, and a web app shows the forecasts.

Read the boxes as in the Phase 1 plan: ticked is done, open is still to do. Depends on:
in brackets.

-   [x] **1 Phase 2 finished**: the open boxes of the Phase 2 plan; every acceptance
    test of phase 2 passes. Blocks items 3 and 7, which need forecasts from a trained
    model served by `predict/` (Phase 1 item 5, Phase 2 item 4), and the retraining of
    item 5 and the webhook of item 6, which need the training pipeline (Phase 2 item 7);
    the other items need neither.
-   [x] **2 Service metrics and dashboard** (REQ-MON-003)
    -   [x] the API reports at `/metrics` the request count, the response time and the
        status group per route, and the trading days behind per security
    -   [x] Prometheus and Grafana in Compose (`make monitoring`) with the dashboard
        "API": requests per second, response time, error rate, trading days behind
    -   [x] each security's latest feature drift and prediction drift results
        (REQ-MON-001, REQ-MON-002) on the dashboard (5)
-   [x] **3 Prediction log** (1; REQ-SVC-003): every forecast, made through the API or a
    command, is stored with its input features, model version and time of request
-   [ ] **4 Outcome collection** (3; REQ-AUT-002): once a predicted day's actual quote
    is stored, it is recorded against each forecast for that day and the production
    error is computed
-   [x] **5 Drift checks and training when needed** (REQ-MOD-006, REQ-MON-001,
    REQ-MON-002, REQ-AUT-001)
    -   [x] training when needed: a security is trained only when it has no recorded
        training, when the feature drift check finds drift, or when at least
        `retraining_interval_days` trading days have been stored since its latest
        training; the feature drift check compares the daily price changes of the latest
        `drift_window_days` stored trading days with those of all days up to the latest
        training, and records its report and p-value as its own MLflow run (1;
        REQ-MOD-006, REQ-MON-001)
    -   [x] scheduled forecasts and the prediction drift check: after training, the
        training pipeline makes one scheduled forecast per configured security; the
        pipeline `prediction_drift_check` has the production model forecast again from
        the inputs of recent scheduled forecasts, and compares these with its forecasts
        for the days up to the security's latest training; when drift is found, every
        configured security is trained (1, 3; REQ-MON-002, REQ-AUT-001)
    -   [x] settings: `drift_window_days`, `prediction_drift_check_interval_days` and
        `drift_p_value_threshold` in `config/drift_checks.toml`,
        `retraining_interval_days` in `config/training.toml`; each service checks their
        ranges when it starts (REQ-AUT-007)
-   [ ] **6 Alerts** (REQ-MON-004, REQ-MON-005)
    -   [x] Grafana raises an alert when the API's error rate crosses its configured
        threshold (2; REQ-MON-004)
    -   [x] Grafana raises an alert when a security is behind by a trading day that was
        final when the latest load ran, or when the daily update is missed (2;
        REQ-MON-004)
    -   [ ] an alert configured to start training calls a webhook that starts the
        training pipeline (1; REQ-MON-005)
-   [x] **7 Web app** (1; REQ-SVC-001, REQ-SVC-005, REQ-SVC-006, REQ-SVC-007,
    REQ-APP-001, REQ-APP-002, REQ-APP-003)
    -   [x] the API lists the configured securities, returns a security's recent closes
        and its production model's results next to the baselines, and refuses a forecast
        for a security without a production model (REQ-SVC-001, REQ-SVC-005,
        REQ-SVC-006, REQ-SVC-007)
    -   [x] the web app shows the forecast view, the notice "not investment advice" on
        every page and the model results next to the baselines (REQ-APP-001,
        REQ-APP-002, REQ-APP-003)
-   [ ] **8 Acceptance tests of phase 3**: written before the code of each item, for
    REQ-MOD-006, REQ-SVC-001, REQ-SVC-003, REQ-SVC-005, REQ-SVC-006, REQ-SVC-007,
    REQ-AUT-002, REQ-MON-001, REQ-MON-002, REQ-MON-005, REQ-APP-001 and REQ-APP-003

## Open questions

-   Split timing: check at which point of a split's own day EODHD applies it when a
    reference security next splits (see [Constraints]).
-   Defense date: one week after the coach meeting of Nov 16, around Mon Nov 23 (coach,
    Oct 22); the SEP26 sheet also lists a mock defense call on Nov 12. The exact day:
    (Ask the coach.)

[Constraints]: ../ARCHITECTURE.md#constraints
[Decisions]: #decisions
[team.md]: team.md
