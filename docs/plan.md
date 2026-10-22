# Financial forecasting — project plan

Reference material: `references/` (index in `references/README.md`).

## Decisions
Settled. Basis: coach feedback, agreed, or built and in use. Longer explanations follow the table.

| Topic | Decision | Basis | Date | Details |
|---|---|---|---|---|
| Database | PostgreSQL; each member's database is private and filled only from EODHD with their own key | Coach feedback (PostgreSQL), agreed (private databases) | Oct 12, 2026 1) | [Database](#database), [`decisions/database.md`](decisions/database.md) |
| Environment | uv; `make setup` installs the locked packages | Coach feedback | Oct 12, 2026 1) | README, "Setup" |
| Team repo | the course repo `DataScientest-Studio/sep26_bmlops_int_financial_pred`, with this project's full history and its own structure | Coach feedback | Oct 12, 2026 1) | — |
| API access | optional, phase 2: HTTP basic authentication against a `users` table, passwords as bcrypt hashes, roles `user` and `admin` | Agreed | Oct 12, 2026 1) | [API access](#api-access), [`decisions/password-hashing.md`](decisions/password-hashing.md) |
| Trading calendar | the `exchange_calendars` package, wrapped in one module of the project | Built | Oct 12, 2026 1) | [`decisions/trading-calendar.md`](decisions/trading-calendar.md) |
| Test strategy | acceptance tests per requirement first, unit tests with the code; pytest with pytest-xdist | Built | Oct 12, 2026 1) | [Test strategy](#test-strategy) |
| Requirements | StrictDoc, top level only (~15–25); source `docs/requirements.sdoc`, `make requirements` regenerates `docs/requirements.md` after every change | Built | Oct 12, 2026 1) | — |
| Continuous integration | every push runs `make lint` and `make test` on GitHub | Built | Oct 12, 2026 1) | [Continuous integration](#continuous-integration) |
| Data source | EODHD, free tier (20 calls per day, 1 year of history); each member uses their own free key; `make load` fills a new database, `make update` adds the new trading days | Agreed | Oct 12, 2026 1) | [Data source](#data-source) |
| Close prices | prices stored as they printed; splits and dividends in tables of their own | Agreed | Oct 12, 2026 1) | [Close prices](#close-prices) |
| Package and login | Python package `forecasting`; development login `admin`/`admin` in `.env.example`, for local use only | Built | Oct 12, 2026 1) | — |
| Model serving | FastAPI; BentoML is not used | Coach feedback | Oct 15, 2026 2) | — |
| Roadmap | milestones and phase plans as written in this plan | Decided (Tobias) | Oct 19, 2026 3) | [Roadmap](#roadmap) |
| Reference securities | six stocks and two market indices, as configured in `config/securities.toml` | Decided (Tobias) | Oct 19, 2026 3) | [Reference securities](#reference-securities) |
| Objectives and key metrics | as drafted in `docs/requirements.sdoc` | Decided (Tobias) | Oct 19, 2026 3) | `requirements.md`, "Objectives", "Key metrics" |
| Local operation | each member runs the whole system on their own machine; no cloud service | Decided (Tobias) | Oct 19, 2026 3) | `requirements.md`, "What the product supports" |
| Replay | replays into a database of its own, one trading day per interval in seconds (a setting) | Decided (Tobias) | Oct 22, 2026 5) | REQ-DAT-003 |
| Dataset versions | a DVC snapshot is a version record of a training dataset, never the store training reads from; DVC runs without Git and keeps every snapshot on the member's own machine, in DVC's own store and in the local object store | Decided (Tobias); DVC optional (coach), kept: Decided (Tobias) | Oct 19, 2026 3), Oct 22, 2026 5), Oct 22, 2026 6) | REQ-CON-003, [Object store](#object-store), [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) item 5 |
| Airflow | Airflow 3.3.2 with the LocalExecutor, its own database on the project's PostgreSQL server; each task calls a service built from the project image: training through the API, loads and replay through a data service reachable only inside Compose | Decided (Tobias) | Oct 21, 2026 4) | [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) |
| Code review | work from a member's own branch reaches `main` through a pull request; an approval is not required yet | Decided (Tobias) | Oct 21, 2026 4) | [Continuous integration](#continuous-integration) |
| Provisional closes | a price fetched while its session runs stands in for the close until a later fetch replaces it; it is final once fetched a set delay after its exchange's close | Built | Oct 22, 2026 5) | [Provisional closes](#provisional-closes), REQ-DAT-007 |
| Scope | level 1 complete (full chain, persistence and mean-change baselines, historical replay, trading calendar) with several securities, plus the level 3 parts the course requires (prediction logging, drift checks, triggered retraining, keep-the-better-model rule); level 2 items (more securities, backtesting) only if the chain is complete by Nov 6 | Decided (Tobias) | Oct 22, 2026 5) | [Roadmap](#roadmap) |
| History to train on | training uses every stored final day of a security; how far back that reaches depends on each member's key and database, so it may differ from machine to machine | Decided (Tobias) | Oct 22, 2026 5) | [Data source](#data-source) |
| Code files | separate modules for features, training, evaluation and prediction in `src/forecasting/` | Built | Oct 22, 2026 5) | — |
| Model store | MLflow's model registry keeps the models; the MLflow server keeps its records in a database of its own on the project's PostgreSQL server and the model files in a local S3-compatible object store, SeaweedFS | Coach feedback (registry, PostgreSQL, separate object store); Decided (Tobias) (SeaweedFS) | Oct 22, 2026 6) | [Object store](#object-store), [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) item 3 |
| Monitoring | Evidently for drift; Prometheus and Grafana for the metrics and the dashboard, API usage included | Coach feedback | Oct 22, 2026 6) | REQ-MON-001–004 |
| Versioning | every training run records the model, the version of the dataset it trained on and the commit of the code it ran, or `unknown` for an image `make` did not build | Coach feedback | Oct 22, 2026 6) | REQ-MOD-004, [Phase 2 plan](#phase-2-plan--the-chain-runs-end-to-end) items 3 and 5 |

1\) As presented: sep26_bmlops_int_financial_pred @ Mon Oct 12, 2026 12pm - 12:30pm (CEST).

2\) Coach answer in the team Slack channel, Oct 15, 2026.

3\) Decided by Tobias as coordinator, Oct 19, 2026.

4\) Decided by Tobias as coordinator, Oct 21, 2026.

5\) Decided by Tobias as coordinator, Oct 22, 2026.

6\) Coach meeting, Oct 22, 2026; the choices the coach left to us decided by Tobias as coordinator, Oct 22, 2026.

### Database
PostgreSQL, details in `decisions/database.md`. Each member runs their own private database, filled only from EODHD with their own key: `make load` once, `make update` every trading day. Price data never leaves a member's machine and is never committed.

### API access
HTTP basic authentication against a `users` table in the project database (passwords stored as bcrypt hashes, see `decisions/password-hashing.md`; role `user` or `admin`). Users call `predict/`; admins also call `training/`, the model metrics and a few user-management endpoints (add, list, remove). The demo app logs in as a user. Builds on the course's API security exercise.

### Test strategy
requirements first. Each requirement names how it is checked: Test, Demonstration or Inspection (`requirements.md`, "How requirements are checked"). For every requirement checked by Test, black-box acceptance tests are written before the code (TDD); the share of passing acceptance tests is the progress indicator (`make acceptance`). Below them: unit tests for the pure functions (features, target, no look-ahead, baselines, metrics, trading calendar), API tests with swapped-in parts, and integration tests against a throwaway database with a small fixed price set. Each pytest-xdist worker gets its own test database; tests never use a cloud service or real e-mail, and never the network, with one exception: the contract tests of the data source (`make contract`) call EODHD with the member's own key from `.env`, to notice when EODHD changes how it delivers data. They are not part of `make test` or CI, and each check the key's history, remaining calls or plan cannot support is skipped with its reason. No model-quality thresholds: tests check that the comparison with the baselines is computed, not that the model wins. Acceptance tests of phase 1 are in `tests/acceptance/`; those of phases 2 and 3 are written when each phase starts.

### Continuous integration
every push runs the style and type checks and the unit tests on GitHub (`.github/workflows/ci.yaml`, the same `make lint` and `make test` as on our machines); a failed run emails the person who pushed. `main` in the course repo refuses deletion and force pushes; work from a member's own branch reaches it through a pull request, which shows the checks of its last push. An approval is not required yet. Nightly runs: later, if needed.

### Data source
EODHD, free tier as of Oct 2026: 20 calls per day, 500 one-time welcome calls on top, and 1 year of history. Prices, splits and dividends all come from EODHD; daily prices cover exchanges worldwide, market indices included. Each member signs up for their own free key and keeps it in their own `.env` (`EODHD_API_KEY`). `make load` loads each security without stored prices from a configured first day (`HISTORY_START`), as far back as the plan allows; `make update` fetches for each security only the days from its latest stored one on, so each run moves little data.

A call is one request for one symbol and one kind of data, however many days it covers. With the reference securities (six stocks, two indices, `config/securities.toml`) every `make load` and every `make update` makes these calls:

| Data | Fetched for | Calls |
|---|---|---|
| Prices from the latest stored day on (from `HISTORY_START` while none is stored) | 6 stocks, 2 indices | 8 |
| Splits, the full list | 6 stocks | 6 |
| Dividends, the full list | 6 stocks | 6 |
| Total | | 20 |

A stock costs three calls, an index one (an index has no splits or dividends). 20 calls is the whole free daily limit, which is why the reference securities stop at six stocks and two indices: a seventh stock would need 23. A free key therefore runs one load or update per day; the welcome calls cover reruns and `make contract` in a member's first days.

EODHD's daily prices include the current day while its session is still running (delayed by about 15 minutes), in the same form as a finished day. How such a row is handled: [Provisional closes](#provisional-closes).

### Provisional closes
During a running session the latest price stands in for the close. Each stored row carries the time it was fetched; a row is final once it was fetched a set delay after its exchange's close (trading calendar, early closes included; the delay, `FINAL_DELAY_MINUTES`, covers EODHD's 15 minutes and the closing auction). A later fetch replaces a provisional row and never a final one. Training uses final rows only; a forecast may start from a provisional close and then says so: the response gives the close it starts from and when that price was fetched. A load during a session stores that day as provisional, and the next load replaces it with the final close.

### Close prices
the database stores prices as they printed — open, high, low, close and volume as traded that day. Splits (ratio) and dividends (amount actually paid, currency) are stored as events in tables of their own; the model's inputs correct prices and volumes for them when the inputs are built. EODHD delivers volume already corrected for each split it has applied; a split it lists for a day after the last delivered day is not yet applied. The load reverses the correction with the split ratios it fetches in the same run (each day's volume divided by the ratios of all later splits up to the last delivered day). When on a split's own day EODHD applies it (before the session opens, during it, or only after the close) is unchecked; it is checked when a reference security next splits. EODHD keeps closes as printed and multiplies the volume before a split by its ratio; the splits API delivers each ratio as text, for example `4.000000/1.000000`.

### Object store
Model files and dataset versions are kept in an S3-compatible object store that runs in Compose on the member's own machine, so price data never leaves it. The coach recommended MinIO; its community edition is no longer maintained and no longer published as an image, so we use SeaweedFS (Apache 2.0 licence, maintained since 2014, the default object store of Kubeflow Pipelines), which offers the same S3 interface. Training and the API send and fetch model files through the MLflow server; DVC copies each dataset version into a bucket of its own.

### Reference securities
Six stocks that behave differently, plus two market indices as reference series (`config/securities.toml`). The indices are loaded like the stocks but are never a forecast target; whether the model uses their recent changes as inputs is part of "First model". Each request covers one symbol and one kind of data (EODHD's requests for a whole exchange cost 100 calls). A load costs three calls per stock (prices, splits, dividends) and one per index (no splits or dividends): 20 calls, the free tier's daily limit. A daily update costs the same when events are checked every day, 8 when only prices are fetched; a fetch during a running session does not fit beside a full daily update on the free tier.

| Security | Exchange | Why |
|---|---|---|
| Apple (AAPL) | XNAS | very large technology company, medium volatility |
| Tesla (TSLA) | XNAS | high volatility: does the model beat "no change" on noisy prices? |
| JPMorgan Chase (JPM) | XNYS | bank, reacts to interest rates |
| Exxon Mobil (XOM) | XNYS | energy, follows oil prices rather than technology |
| Coca-Cola (KO) | XNYS | defensive, low volatility |
| SAP (SAP) | XETR | second exchange with its own holidays, prices in euro |
| S&P 500 index | XNYS | market trend of the US stocks |
| DAX index | XETR | market trend of the German stock |

## Decision proposals
To be decided by the team.
- First model: at most 1–2 days of model work (coach), then on to the MLOps parts. Proposal: Ridge regression (scikit-learn) predicting the next-day change, always scored next to the two required baselines (persistence: predicted change 0; historical mean change). Features from the price history only: changes of the last 1–5 days, 5- and 20-day volatility, volume change. Metrics: MAE, skill against persistence, directional accuracy, on days after the training period. Candidates with pros and cons: `decisions/regressors.md`. Owner: Scheima, who decides.
- Better model: which newly trained model replaces a security's production model; the Model area decides. A security's first model always becomes its production model.
  Alternatives:
  - Lower error than the production model: the new model is promoted only if its mean absolute error on the evaluation window (for example the last 60 trading days) is lower than the production model's on the same days; a tie keeps the production model. Simple, and both models are scored on the same days.
  - Lower error, and better than "no change": as above, and the new model must also beat the persistence baseline on those days; a model that loses to "no change" is never promoted.
  - Lower error by a margin (for example 1 %): avoids swapping models over differences that are only noise; the margin becomes a setting.
- Secured entry point (phase 3, after the required phase 3 items; the kick-off deck lists "Secured APIs" and "light scalability" for phase 3, the coach lists API security as optional): Nginx in front of the API and the demo app as the only published entry point, with HTTPS (self-signed certificate, since the system runs locally), rate limits on `predict/` and `training/`, and requests spread over several API instances.
  Alternatives:
  - Nginx in front (proposed): encrypts the basic-auth password on the way, stops request floods and shows simple scaling, all with one component; one more service and a certificate to manage.
  - HTTPS in the API server itself (uvicorn): encryption only; no rate limits or scaling, and each service needs its own certificate.
  - Access control only (REQ-SVC-004), no encryption: no extra work; enough while everything runs on one machine (REQ-CON-002), but the password travels readable over any network.
- Demo app: the app the jury sees at the defense; it calls the model API, and the presentation can run inside it. Any technology is accepted.
  Alternatives:
  - Streamlit (proposed): pure Python, as in the course material and past group projects; quick to build, with charts included.
  - Small web app (an HTML page served by FastAPI): no extra framework; layout and charts are written by hand.
  - Gradio: as quick as Streamlit, but aimed at a single model demo; weaker for pages with price history and model metrics.

## Roadmap
Team setup and areas: `docs/team.md`.

Target application, as the jury sees it at the defense: a demo app that calls the model API (see "Demo app" in "Decision proposals").
- Pick a security; see its next-day forecast with the model version, next to both baselines; the "not investment advice" notice always visible.
- A history chart of past forecasts against the actual outcomes.
- A status panel: latest stored quote, latest training run, current production model, latest drift check.

Live demo: replay advances the simulated calendar by a few trading days and the chain runs on its own — new quotes are loaded, predictions logged, drift checked, the model retrained and promoted if it is better — visible in the app, MLflow and Grafana.

| Period | Milestone | Content |
|---|---|---|
| until Mon Oct 12 (coach meeting 12:00) | Foundations: a clone plus `make` gives a database with history, a trained baseline and an API answering `predict/` | "Phase 1 plan" below; roadmap and team setup agreed |
| Oct 13–22 (coach meeting) | Phase 1 finished and the first phase 2 piece | open items of the "Phase 1 plan"; the agreed "Phase 2 plan" |
| Oct 23–29 | Chain runs end to end: one replayed day goes from new quotes through training and promotion to the API serving the new model | MLflow tracking and registry, "better model" rule, Docker Compose services (database, API, object store, MLflow, Airflow), Airflow DAGs for ingestion and training, replay and trading calendar, DVC snapshots with hashes and the code's commit in MLflow; items in "Phase 2 plan" |
| Oct 30–Nov 6 | Closed loop and monitoring | prediction log and outcome collection, Evidently drift DAGs (training and prediction side), Prometheus and Grafana with API usage, alerts and the retraining webhook, first demo app version |
| Nov 7–11 | Feature freeze Nov 11 | tests, README and API docs, check from a fresh clone, demo script |
| Thu Nov 12 | Mock defense call | full demo as at the defense |
| Nov 13–15 | Polish | fixes from the mock defense, presentation (slides or in the demo app) |
| Mon Nov 16 | Coach meeting: phase 3 check | full demo; the coach's findings become the fix list |
| Nov 17–22 | Fix and rehearse | fixes from the coach meeting, 1–2 rehearsals with equal speaking time |
| about Mon Nov 23 | Defense | one week after the coach meeting; the exact day is set by the coach |

Level 2 items (more securities, backtesting) start only if the chain is complete by Nov 6.

## Phase 1 plan — foundations by Mon Oct 12
Proposal for the team. Coach meeting Mon Oct 12, 12:00 (invite sent; a time that does not suit is moved on request in Slack).

Goal: a teammate runs `git clone` and a handful of `make` commands and gets a running database with price history, a trained baseline model, and an API answering `predict/`.

Each item lists what makes it done; a ticked box is done, an open box is still to do. Depends on: in brackets.

- [ ] **0 Team meeting** (before Oct 12; held Oct 11)
  - [x] roadmap decided (Tobias, Oct 19)
  - [ ] organisational setup agreed (see Open)
  - [x] database and data source decided
  - [x] securities decided (Tobias, Oct 19; see "Reference securities")
  - [x] objectives and key metrics (`docs/requirements.sdoc`) decided (Tobias, Oct 19)
- [x] **1 Repo ready and shared** (0)
  - [x] every member invited to write access; closed (Tobias, Oct 19)
  - [x] own repo structure (coach feedback, see [Decisions](#decisions), note 1)
  - [x] template README replaced
  - [x] `.gitignore` and `.env.example` in place
  - [x] CI passes (see "Continuous integration")
- [ ] **2 Reproducible environment** (1)
  - [x] `pyproject.toml`, `uv.lock`, `.python-version`; works from a fresh clone
  - [x] Makefile targets `setup`, `db`, `load`, `update`, `api`, `test`
  - [ ] Makefile targets `train`, `predict`, run in the project image like the other commands; trained models are kept in the project's `models/` folder (gitignored) until MLflow stores them (Phase 2, item 3)
- [x] **3 PostgreSQL** (2): Compose file with only the database (exact image tag, data volume, credentials from `.env`); table `prices` keyed by (security, day)
- [x] **4 One-time load script** (3, data source): loads the history of the agreed securities; a re-run creates no duplicates; API key read from `.env`
- [ ] **5 Baseline training pipeline** (3; 4 for real data)
  - [x] `read_prices` reads the stored prices of one security
  - [ ] a training function builds the target (next-day change), trains, compares with the persistence and mean-change baselines, saves the model under `MODEL_DIR`
  - [ ] a prediction function returns the next-day forecast for one security
  - [ ] unit tests for feature building
  - [ ] the acceptance tests of REQ-MOD-001–003 pass
- [ ] **6 Initial API endpoints** (5)
  - [x] FastAPI routes `training/` (runs training) and `predict/` (security in; forecast and model version out), wired to the training and prediction functions; unknown symbols refused
  - [ ] the acceptance tests of REQ-SVC-001/002 pass
- [x] **7 Minimum tests and docs** (2–6)
  - [x] README section "Setup", from a fresh clone
  - [x] unit tests run in parallel with pytest-xdist; both endpoints covered by the acceptance tests of REQ-SVC-001/002

Repo sharing (item 1): every member works with their own GitHub account; access is granted to the accounts, never shared. Each member brings their GitHub username to the meeting.
- Team repo: the course repo `DataScientest-Studio/sep26_bmlops_int_financial_pred`, holding this project's full history. Members get write access by invitation from an admin of the repo.
- A ruleset on `main` refuses deleting it and force pushes; GitHub enforces it because the course repo is public. How changes reach `main`: [Continuous integration](#continuous-integration).

Interfaces to agree at the meeting, so items 3–6 can be built in parallel:
- Table: `prices(symbol, day, open, high, low, close, volume, fetched_at)`, primary key (symbol, day); `fetched_at` is the time the row was fetched (UTC), see [Provisional closes](#provisional-closes).
- Tables: `splits(symbol, day, ratio)` and `dividends(symbol, day, amount, currency)`, primary key (symbol, day) each.
- Functions: `train() -> model_version`, `predict(symbol) -> forecast`.
- API: request and response of `training/` and `predict/`.

Split: by area (data, model, service), see `docs/team.md`.

In Phase 1 the model is saved as a plain file; MLflow follows in Phase 2 (see "Roadmap").

## Phase 2 plan — the chain runs end to end
Coach meeting Thu Oct 22 (a progress check, not a submission): phase 1 finished and the first piece below. The chain is complete by Oct 29.

Goal: Airflow starts the chain on a schedule and it runs with no manual step — new quotes (in a demo: replayed history) reach the database, a model is trained on them, MLflow records the run, the new model is promoted if it beats the production model, and the API serves the production model. `docker compose up` starts all of it.

Course checklist for this phase (`references/course-checklist.md`): MLflow tracking and model registry; compare each new run with the previous model and tag the best; Docker microservices with Compose; scheduled training (Airflow recommended); DVC without Git, dataset hashes stored in MLflow. Optional: unit tests and CI, API security, Kubernetes.

Each item is one complete piece that fits the interfaces below; it is merged only when it works. Depends on: in brackets.

- [ ] **1 Phase 1 finished**: the open boxes of the Phase 1 plan; every acceptance test of phase 1 passes. Blocks items 3 and 4 and the training pipeline of item 7; the other items need no trained model.
- [x] **2 Project image and `api` service** (REQ-AUT-003, REQ-AUT-005, REQ-AUT-006)
  - [x] one image holds the project's code and its locked packages; the commands run from it
  - [x] Compose runs the API from it next to the database; the commands and the API share the project's `models/` folder
  - [x] paths (securities file, `db/init`) do not depend on the folder a command starts in
- [ ] **3 MLflow tracking** (2; 1 for training runs; REQ-MOD-004)
  - [x] the object store, SeaweedFS, in Compose: an exact image version, its data in a volume, no published port
  - [x] the MLflow server in Compose: its records in the database `mlflow` on the project's PostgreSQL server, its model files in the object store, its page on `127.0.0.1:${MLFLOW_PORT}`; the API and the commands reach it inside Compose
  - [ ] the project image carries the commit it was built from: `make` passes it in when it builds the image, a build from a tree with uncommitted changes says so, and a build `make` did not start records the code version as `unknown`
  - [ ] every training run records its parameters, metrics, dataset version, code version and model (1)
  - [ ] MLflow is the model store; the `models/` folder and `MODEL_DIR` are removed (1)
- [ ] **4 Registry and promotion** (3; REQ-MOD-005, REQ-SVC-001/002)
  - [ ] one registered model per security
  - [ ] a new model becomes production only if it is better by the rule chosen in "Better model" (Decision proposals); the first model always becomes production
  - [ ] `predict/` uses the production model; the training response says whether the model was promoted
- [ ] **5 Dataset version** (3 for the MLflow record; REQ-DAT-006)
  - [x] `dataset_version` writes the rows it is given, without row numbers, to `datasets/<symbol>.csv`, records the file with DVC without Git and returns DVC's fingerprint of it as the version id; the same rows always get the same id, in the member's own database and in the replay database alike
  - [ ] before training a security, training passes the rows it trains on to `dataset_version`
  - [x] each distinct dataset is kept as a full copy in DVC's store on the member's own machine, so a dataset can be brought back by its id; no remote outside the member's own machine (price data never leaves it), and older copies are never deleted, since without Git DVC's clean-up would remove them; the snapshot is a record, training reads from the database
  - [x] DVC copies each dataset version into the object store (item 3)
  - [ ] MLflow records it with the run
- [x] **6 Replay** (7 for the interval; REQ-DAT-003)
  - [x] `make replay` copies the next day from the member's own database into a database of its own, named after it with `_replay`: prices with their fetch times, splits and dividends, unchanged; the next day is the first stored day after the replay database's latest day; each run copies the replay database's latest day again, so a final quote replaces a provisional one, and copies all or nothing; the replay database's latest day is the simulated today
  - [x] the first run creates the replay database and fills it up to `REPLAY_START` (between the first and the latest stored day); at the latest stored day there is nothing left to replay; `make replay-reset` deletes the replay database, so the next run starts over from `REPLAY_START`; with nothing stored, replay is refused
  - [x] the member's own database is only read; replay makes no EODHD calls
  - [x] the replay interval (`REPLAY_INTERVAL_SECONDS`, within the limits of REQ-DAT-003) sets the schedule of the replay pipeline (item 7)
- [ ] **7 Airflow** (2; 4 for training; 6 for replay; REQ-AUT-001, REQ-DAT-003)
  - [x] Airflow 3.3.2 in Compose, LocalExecutor, with its own database `airflow` on the project's PostgreSQL server, created when missing, and its own login, which owns only that database; its page on `127.0.0.1:${AIRFLOW_PORT}`, with a login for one admin user, whose password is set in `.env`
  - [x] each task calls a service built from the project image over the Compose network, so Airflow's own image holds none of the project's packages and needs no access to Docker; Airflow receives only the settings its pipelines read, never the EODHD key
  - [x] data service: `POST /load` runs the load and answers with its report, `POST /replay` copies the next day and answers with it (none when nothing is left); reachable only inside Compose
  - [x] daily update pipeline: one load on weekdays at 16:00 New York time plus `FINAL_DELAY_MINUTES`; never retried, since one load uses the free tier's day
  - [x] replay pipeline: one replayed day every `REPLAY_INTERVAL_SECONDS` seconds
  - [x] both pipelines start paused, the operator unpauses one of them; neither catches up on missed runs, and each runs once at a time
  - [x] both pipelines announce their work: the daily update after each load as the asset `prices`, also after one that found no new trading day; the replay pipeline after each replayed day as the asset `replay-prices`; a skipped or failed run announces nothing
  - [ ] training pipeline: train, then promote, for each security. While replay runs, training, forecasts and the API read the replay database, never the member's own; models trained during replay are kept apart from the member's own models (for example their own registered names, `replay-forecast-AAPL.US`); the pipeline starts on either asset; the mode follows the unpaused ingestion pipeline
- [ ] **8 Acceptance tests of phase 2**: written before the code of each item, for REQ-DAT-003, REQ-DAT-006, REQ-MOD-004, REQ-MOD-005, REQ-AUT-003 and REQ-AUT-005

Optional, after item 7: API access (REQ-SVC-004), CI building the images (REQ-AUT-004).

Interfaces to agree first, so items 2–7 can be built in parallel:
- Commands: `load` (`make load` and `make update`), `replay`, `replay-reset`, `train`, `promote` (each `python -m forecasting.commands <name>` run in the project image, and a `make` target); Airflow calls the same functions through the services: `load` and `replay` through the data service, `train` and `promote` through the API.
- Registered model names: one per security, for example `forecast-AAPL.US`.
- Assets: `prices` (after each load of the member's own database), `replay-prices` (after each replayed day in the replay database).
- Functions: `dataset_version(settings, symbol, rows) -> version id`, called by training with the rows it trains on, before it trains; MLflow records the id with the run.
- Settings: MLflow page port (`MLFLOW_PORT`), evaluation window (its default is chosen with "Better model"), replay interval (`REPLAY_INTERVAL_SECONDS`), Airflow page port (`AIRFLOW_PORT`). The daily update's time follows from the US close and `FINAL_DELAY_MINUTES`.
- Code version: the commit the project image was built from; `unknown` when `make` did not build it.

## Open
- Organisational setup: proposal in `docs/team.md` (areas and owners, meetings, communication, work tracking, reviews), to be agreed by the team.
- Defense date: one week after the coach meeting of Nov 16, around Mon Nov 23 (coach, Oct 22); the SEP26 sheet also lists a mock defense call on Nov 12. The exact day: (Ask the coach.)
